import enum
import logging

from telegram import (
    InlineKeyboardMarkup,
    Update,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

from database import SessionLocal, VoterRecord
import config


logger = logging.getLogger(__name__)


# Set the logging level to DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Define states for the ConversationHandler
(
    MENU_CHOICE,
    LISTED_TX_FOR_VERIFICATION,
    REMOVE_TX_REQUESTED_INPUT,
    REMOVE_TX_REQUESTED_CONFIRMATION,
    REGION,
    READY_TO_SEND_TX,
    MOSCOW_TRANSACTION_ID,
    OTHER_TRANSACTION_ID,
    OTHER_VOTER_KEY,
    CONFIRMATION,
    CONFIRMATION_RESPONSE_HANDLER,
) = range(11)


async def menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    force_new_message: bool = False,
) -> int:
    del context
    keyboard = [
        [
            InlineKeyboardButton(
                "Add a transaction to verification",
                callback_data="add_tx_for_verification",
            ),
            InlineKeyboardButton(
                "List currently checked transactions",
                callback_data="list_tx_for_verification",
            ),
        ],
    ]

    query = update.callback_query
    message = update.message
    if message is None:
        assert query is not None
        assert query.message is not None
        message = query.message

    fn_to_use = message.reply_text
    if not force_new_message and query is not None:
        fn_to_use = query.edit_message_text

    await fn_to_use(
        "Welcome! This bot allows you to check if your ballot was "
        "counted in the Russian elections in 2024. "
        "If something goes wrong, type /cancel to go back to the menu. "
        "Choose a command:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return MENU_CHOICE


def _format_voting_record(record: VoterRecord, tx_number: int) -> str:
    message = f"Transaction #{tx_number}:\n"
    message += f"Region: {record.region}\n"
    message += f"Transaction ID: {record.transaction_id}\n"
    if record.region == "other":
        message += f"Voter key: {record.voter_key}\n"
    return message


async def list_tx_for_verification(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    assert context.user_data is not None

    query = update.callback_query
    assert query is not None
    assert query.message is not None

    with SessionLocal() as session:
        all_this_user_records = (
            session.query(VoterRecord)
            .filter(VoterRecord.user_id == query.from_user.id)
            .all()
        )

    await query.answer()

    n_records = len(all_this_user_records)
    if n_records == 0:
        await query.message.reply_text("You don't have any transactions to verify yet.")
        return await menu(update, context, force_new_message=True)

    message = f"Currently verified transactions: {n_records}.\n\n"

    for i, record in enumerate(all_this_user_records, 1):
        message += _format_voting_record(record, i) + "\n"

    message += "Do you want to remove some of the transactions from monitoring?"

    context.user_data["tx_for_removal"] = {
        i: record.id for i, record in enumerate(all_this_user_records, 1)
    }

    await query.edit_message_text(
        message.strip(),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Yes", callback_data="remove_tx")],
                [InlineKeyboardButton("No, go back to menu", callback_data="menu")],
            ]
        ),
    )

    return LISTED_TX_FOR_VERIFICATION


async def remove_tx_request_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    assert context.user_data is not None
    query = update.callback_query
    assert query is not None
    assert query.message is not None

    tx_for_removal = context.user_data["tx_for_removal"]

    await query.answer()

    await query.edit_message_reply_markup(reply_markup=None)

    all_keyboard_buttons = []
    for tx_number in tx_for_removal.keys():
        all_keyboard_buttons.append(
            InlineKeyboardButton(f"{tx_number}", callback_data=f"delete_{tx_number}")
        )

    organized_keyboard_buttons = []
    for batch_start in range(0, len(all_keyboard_buttons), 3):
        organized_keyboard_buttons.append(
            all_keyboard_buttons[batch_start : batch_start + 3]
        )

    organized_keyboard_buttons.append(
        [
            InlineKeyboardButton("Go back", callback_data="back"),
        ]
    )

    await query.message.reply_text(
        "Which transaction do you wish to remove?",
        reply_markup=InlineKeyboardMarkup(organized_keyboard_buttons),
    )

    return REMOVE_TX_REQUESTED_INPUT


async def remove_tx_request_confirmation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert context.user_data is not None
    query = update.callback_query
    assert query is not None
    assert query.message is not None
    await query.answer()

    tx_to_delete = query.data
    assert isinstance(tx_to_delete, str) and tx_to_delete.startswith("delete_")
    tx_number_to_delete = int(tx_to_delete.split("_")[1])

    context.user_data["deleting_tx"] = tx_number_to_delete

    tx_for_removal = context.user_data["tx_for_removal"]
    tx_id_for_removal = tx_for_removal[tx_number_to_delete]

    with SessionLocal() as session:
        tx_to_delete = session.query(VoterRecord).get(tx_id_for_removal)
        assert tx_to_delete is not None

    message = "About to delete transaction:\n"
    message += _format_voting_record(tx_to_delete, tx_number_to_delete) + "\n"

    message += "Are you sure?"

    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes", callback_data="yes"),
                    InlineKeyboardButton("No, go back", callback_data="no"),
                ]
            ]
        ),
    )

    return REMOVE_TX_REQUESTED_CONFIRMATION


async def remove_tx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    query = update.callback_query
    assert query is not None
    assert query.message is not None

    tx_for_removal = context.user_data["tx_for_removal"]
    tx_number_to_delete = context.user_data["deleting_tx"]
    tx_id_for_removal = tx_for_removal[tx_number_to_delete]

    with SessionLocal() as session:
        with session.begin():
            tx_to_delete = session.query(VoterRecord).get(tx_id_for_removal)
            if tx_to_delete:
                session.delete(tx_to_delete)

    await query.answer()

    await query.edit_message_text(
        f"Successfully deleted transaction #{tx_number_to_delete}",
        reply_markup=None,
    )
    return await menu(update, context, force_new_message=True)


async def start_record_tx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None
    context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("Moscow", callback_data="moscow")],
        [InlineKeyboardButton("Other", callback_data="other")],
        [InlineKeyboardButton("Back to menu", callback_data="back_to_menu")],
    ]

    query = update.callback_query
    assert query is not None
    assert query.message is not None

    await query.answer()

    await query.edit_message_text(
        "You want us to check if your ballot was accounted for correctly "
        "in the electronic elections in Russia."
        " Please choose your region:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return REGION


class UserRegion(enum.Enum):
    MOSCOW = "moscow"
    OTHER = "other"


async def region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert context.user_data is not None

    query = update.callback_query
    assert query is not None
    await query.answer()

    user_region = query.data
    context.user_data["region"] = user_region

    if user_region == "moscow":
        context.user_data["region"] = UserRegion.MOSCOW
        keyboard = [
            [
                InlineKeyboardButton(
                    "Send SID for Moscow election",
                    callback_data="send_sid_moscow",
                )
            ]
        ]
        await query.edit_message_text(
            text='Please check the checkbox "Get address of an encrypted transaction with the vote".',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        # Send the screenshot for Moscow here
        return READY_TO_SEND_TX
    elif user_region == "other":
        context.user_data["region"] = UserRegion.OTHER
        keyboard = [
            [
                InlineKeyboardButton(
                    "Send transaction ID and voter key for regional election",
                    callback_data="send_id_key_other",
                )
            ]
        ]
        await query.edit_message_text(
            text="After voting, you need to record the transaction ID and the public voter key.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        # Send the screenshot for other regions here
        return READY_TO_SEND_TX

    raise ValueError("Invalid user region, this is not supposed to happen")


async def ready_to_send_tx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query

    assert query is not None
    assert query.message is not None
    assert context.user_data is not None

    await query.answer()

    region = context.user_data["region"]
    await query.edit_message_reply_markup(reply_markup=None)
    match region:
        case UserRegion.MOSCOW:
            await query.message.reply_text(
                "Please send the transaction SID in the response that you get after the voting",
            )
            return MOSCOW_TRANSACTION_ID
        case UserRegion.OTHER:
            await query.message.reply_text(
                "Please send the transaction SID and voter key in the response that you get after the voting",
            )
            return OTHER_TRANSACTION_ID
        case _:
            await query.message.reply_text(
                "Something went wrong, sending back to main menu"
            )
            return await menu(update, context, force_new_message=True)


async def moscow_transaction_id(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message is not None
    assert update.message.text is not None
    assert context.user_data is not None
    transaction_id = update.message.text

    context.user_data["transaction_id"] = transaction_id
    return await confirmation(update, context)


async def other_transaction_id(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message is not None
    assert update.message.text is not None
    assert context.user_data is not None
    transaction_id = update.message.text
    context.user_data["transaction_id"] = transaction_id
    await update.message.reply_text(
        "Now, please provide your public voter key in the response."
    )
    return OTHER_VOTER_KEY


async def other_voter_key(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message is not None
    assert update.message.text is not None
    assert context.user_data is not None
    voter_key = update.message.text
    context.user_data["voter_key"] = voter_key
    return await confirmation(update, context)


async def confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    assert update.message is not None
    assert context.user_data is not None

    user_region = context.user_data.get("region")
    transaction_id = context.user_data.get("transaction_id")
    voter_key = context.user_data.get("voter_key")

    assert user_region is not None
    assert transaction_id is not None
    if user_region == UserRegion.OTHER:
        assert voter_key is not None

    await update.message.reply_text(
        f"Here is your information:\nRegion: {user_region.value}\nTransaction ID: {transaction_id}\nVoter Key: {voter_key}\n\nIs this correct?",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Yes, I confirm everything is correct",
                        callback_data="correct",
                    ),
                    InlineKeyboardButton(
                        "No, go back to menu",
                        callback_data="incorrect",
                    ),
                ]
            ],
        ),
    )
    return CONFIRMATION_RESPONSE_HANDLER


async def confirmation_response_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query

    assert query is not None
    assert query.message is not None
    assert context.user_data is not None

    await query.answer()

    confirm_response = query.data

    if confirm_response == "correct":
        await query.edit_message_reply_markup(reply_markup=None)
        await save_voter_record(update, context)
        return await menu(update, context, force_new_message=True)
    elif confirm_response == "incorrect":
        await query.edit_message_reply_markup(reply_markup=None)
        assert context.user_data is not None
        context.user_data.clear()
        await query.message.reply_text("OK, going back to main menu. Try again.")
        return await menu(update, context, force_new_message=True)

    await query.message.reply_text("Please respond with a correct message.")
    return await confirmation(update, context)


async def save_voter_record(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    assert query is not None
    assert query.message is not None
    assert context.user_data is not None
    assert update.effective_user is not None

    region = context.user_data.get("region")
    transaction_id = context.user_data.get("transaction_id")
    voter_key = context.user_data.get("voter_key")

    assert region is not None
    assert transaction_id is not None
    if region == UserRegion.OTHER:
        assert voter_key is not None

    new_record = VoterRecord(
        user_id=update.effective_user.id,
        transaction_id=transaction_id,
        voter_key=voter_key,
        region=region.value,
    )

    with SessionLocal() as session:
        with session.begin():
            logging.info(f"Persisting voter record: {new_record}")
            session.add(new_record)

    await query.message.reply_text("Thank you! Your details have been recorded.")


def main() -> None:
    application = Application.builder().token(config.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", menu), CommandHandler("menu", menu)],
        states={
            MENU_CHOICE: [
                CallbackQueryHandler(
                    start_record_tx, pattern="^add_tx_for_verification$"
                ),
                CallbackQueryHandler(
                    list_tx_for_verification, pattern="^list_tx_for_verification$"
                ),
            ],
            LISTED_TX_FOR_VERIFICATION: [
                CallbackQueryHandler(menu, pattern="^menu$"),
                CallbackQueryHandler(remove_tx_request_input, pattern="^remove_tx$"),
            ],
            REMOVE_TX_REQUESTED_INPUT: [
                CallbackQueryHandler(menu, pattern="^back$"),
                CallbackQueryHandler(
                    remove_tx_request_confirmation, pattern=r"^delete_\d+$"
                ),
            ],
            REMOVE_TX_REQUESTED_CONFIRMATION: [
                CallbackQueryHandler(remove_tx, pattern="^yes$"),
                CallbackQueryHandler(remove_tx_request_input, pattern="^no$"),
            ],
            REGION: [
                CallbackQueryHandler(region, pattern="^(moscow|other)$"),
                CallbackQueryHandler(menu, pattern="^back_to_menu$"),
            ],
            READY_TO_SEND_TX: [
                CallbackQueryHandler(
                    ready_to_send_tx, pattern="^(send_sid_moscow|send_id_key_other)$"
                )
            ],
            MOSCOW_TRANSACTION_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, moscow_transaction_id)
            ],
            OTHER_TRANSACTION_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, other_transaction_id)
            ],
            OTHER_VOTER_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, other_voter_key)
            ],
            CONFIRMATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirmation),
            ],
            CONFIRMATION_RESPONSE_HANDLER: [
                CallbackQueryHandler(confirmation_response_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", menu)],
    )

    application.add_handler(conv_handler)

    application.run_polling()


if __name__ == "__main__":
    main()
