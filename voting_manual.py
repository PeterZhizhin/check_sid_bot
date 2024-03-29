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


SELECT_REGION = "select_region"
MOSCOW_TELL_ME_ABOUT_CHECKBOX = "moscow_tell_me_about_checkbox"
OTHER_TELL_ME_ABOUT_TRANSACTION_CHECK = "other_tell_me_about_transaction_check"


async def voting_manual_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    query = update.callback_query
    assert query is not None
    assert query.message is not None

    await query.edit_message_text(
        text="""
Отличный вопрос!
Это может показаться удивительным, однако, в ДЭГ можно не очень сложно убедиться, что ваш голос был учтён системой. 
Проверять свой голос очень важно. Если избиратели не будут этого делать, то система ДЭГ сможет выдать любой результат.

На данный момент применяются две системы ДЭГ. Первая: московская, разработанная ДИТ Москвы. Вторая: федеральная, разработанная Ростелекомом.
Чтобы я рассказал вам про ДЭГ в вашем регионе, выбирете его из списка ниже.
""".strip(),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="Москва", callback_data="moscow"),
                ],
                [
                    InlineKeyboardButton(text="Другие регионы", callback_data="other"),
                ],
            ]
        ),
    )

    return SELECT_REGION


async def region_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    del context
    query = update.callback_query
    assert query is not None
    assert query.message is not None

    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    if query.data == "moscow":
        await query.message.reply_text(
            """
В 2022 году разработчики системы добавили функцию, которую просили многие наблюдатели: возможность проверки учёта своего голоса.

Для этого во время голосования избирателю необходимо поставить отдельную галочку "Хочу получить адрес зашифрованной транзакции в блокчейне". Если она стоит, то на странице с завершением голосования избиратель получает уникальный номер, позволяющий проверить, засчитала ли система этот голос. А после подсчёта - проверить, за какого кандитата в итоге этот голос ушёл.

На словах звучит хорошо. На деле, однако, вместе с добавлением этой функции разработчики убрали возможность независимо подвести итоги голосования. Если в 2021 году и раньше наблюдатели за ДЭГ смогли скачать базу данных со всеми голосами и независимо произвести расшифровку, то сейчас это сделать невозможно.

Более того, проверка учёта своего голоса на данный момент устроена так, что система ДЭГ записывает в своих базах данных информацию о том, поставил ли галочку проверки своего голоса избиратель или нет. Из-за этого, к сожалению, фальсификации можно производить автоматически и практически незаметно для наблюдателей. Для этого, во время подведения итогов, достаточно просто посмотреть, поставил ли эту галочку избиратель или нет. Если не поставил, то голос можно сразу переписать за Путина. Если поставил, то засчитываем голос честно: всё равно почти никто этой функцией не пользуется.

В итоге мы наблюдаем следующую картину: наблюдатели не могут независимо подвести итоги, а организаторы выборов могут фальсифицировать голоса практически незаметно.

Поэтому крайне важно, чтобы избиратели в Москве проверяли свой голос. И проверяли, что их голос не подменили на расшифровке.

При голосовании в Москве вы можете проверить, за кого был учтён ваш голос. Этот бот призван упростить проверку.
""".strip(),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Расскажи подробнее про галочку проверки своего голоса"
                        )
                    ]
                ]
            ),
        )
        return MOSCOW_TELL_ME_ABOUT_CHECKBOX
    elif query.data == "other":
        await query.message.reply_text(
            """
В регионах кроме Москвы применяется система, разработанная Ростелекомом.

Разработчики используют, так называемое, Гомоморфное шифрование. Это тип шифрования, когда данные шифруются так, что можно производить над ними математические операции, не расшифровывая их.

Из-за этого системе не требуется расшифровывать каждый голос, чтобы подвести итоги. Вместо этого она складывает все голоса в зашифрованном виде и подводит итоговый результат в виде сразу готового протокола.

На практике эта же схема шифрования является и слабым местом системы. Не нашлось ещё человека, независимого от Ростелекома, который бы достоверно подтвердил, что в используемых схемах шифрования нет закладок, которые бы позволили подделать результаты.

Более того, чтобы защитить систему от наблюдения, Ростелеком ввёл второй ключ расшифровки. Этот ключ не публикуется в Интернете, и не доступен ни наблюдателям, ни членам избирательной комиссии.

При голосовании в системе Ростелекома избиратель может проверить, что его голос попадает в итоговую сумму. Однако, он не может проверить, за кого был учтён его голос. Этот бот призван упростить проверку.
""".strip(),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Расскажи подробнее как узнать, учла ли мой голос система",
                        )
                    ]
                ]
            ),
        )
        return OTHER_TELL_ME_ABOUT_TRANSACTION_CHECK

    raise ValueError(f"Unexpected data {query.data}")


async def moscow_tell_me_about_checkbox(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    del context
    query = update.callback_query
    assert query is not None
    assert query.message is not None
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        """
Когда будете голосовать в Москве обязательно поставьте галочку "Хочу получить адрес зашифрованной транзакции в блокчейне". Это позволит вам проверить, учтён ли ваш голос и за кого он учтён.
""".strip(),
    )
