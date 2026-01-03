"""Onboarding flow for new users"""
import logging
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram_i18n import I18nContext

from notifications import set_user_language, set_user_ui_language, set_user_group, LANGUAGE_OPTIONS
from utils import format_group_display
from .states import OnboardingStates
from .callbacks import build_language_keyboard
from . import router

logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("onboard_ui_lang_"))
async def handle_onboarding_ui_language_select(callback: CallbackQuery, i18n: I18nContext):
    """Handle bot UI language selection at start of onboarding"""
    user_id = callback.from_user.id

    # Extract language code (en or ru)
    ui_lang = callback.data.replace("onboard_ui_lang_", "")

    # Set UI language
    if set_user_ui_language(user_id, ui_lang):
        logger.info(f"User {user_id} selected UI language: {ui_lang}")

    # Now show GPRO language selection (existing flow)
    keyboard = build_language_keyboard(page=1, current_lang='gb', onboarding=True, i18n=i18n)

    await callback.message.edit_text(
        i18n.get("start-welcome-new"),
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboard_lang_page_"))
async def handle_onboarding_language_page(callback: CallbackQuery, i18n: I18nContext):
    """Handle language pagination during onboarding"""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer(i18n.get("error-invalid-page"), show_alert=True)
        return

    keyboard = build_language_keyboard(page=page, current_lang='gb', onboarding=True, i18n=i18n)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("onboard_lang_") & ~F.data.in_(["onboard_lang_page_1", "onboard_lang_page_2", "onboard_lang_page_3", "onboard_lang_page_4"]))
async def handle_onboarding_language_select(callback: CallbackQuery, i18n: I18nContext):
    """Handle language selection during onboarding"""
    user_id = callback.from_user.id

    # Extract language code
    lang_code = callback.data.replace("onboard_lang_", "")

    # Set user language
    if set_user_language(user_id, lang_code):
        lang_display = LANGUAGE_OPTIONS.get(lang_code, lang_code)
        await callback.answer(i18n.get("feedback-language-set", language=lang_display))
    else:
        await callback.answer(i18n.get("error-invalid-language"), show_alert=True)
        return

    # Proceed to group selection
    await show_onboarding_group_menu(callback.message, user_id, i18n)


@router.callback_query(F.data == "onboard_skip_lang")
async def handle_onboarding_skip_language(callback: CallbackQuery, i18n: I18nContext):
    """Skip language selection during onboarding"""
    user_id = callback.from_user.id
    await callback.answer(i18n.get("feedback-skip-language"))

    # Proceed to group selection
    await show_onboarding_group_menu(callback.message, user_id, i18n)


async def show_onboarding_group_menu(message: Message, user_id: int, i18n: I18nContext):
    """Show group selection menu during onboarding"""
    keyboard_buttons = [
        [
            InlineKeyboardButton(text=i18n.get("button-group-elite"), callback_data="onboard_group_E"),
            InlineKeyboardButton(text=i18n.get("button-group-master3"), callback_data="onboard_group_M3")
        ],
        [
            InlineKeyboardButton(text=i18n.get("button-group-pro15"), callback_data="onboard_group_P15"),
            InlineKeyboardButton(text=i18n.get("button-group-amateur42"), callback_data="onboard_group_A42")
        ],
        [
            InlineKeyboardButton(text=i18n.get("button-group-rookie11"), callback_data="onboard_group_R11")
        ],
        [
            InlineKeyboardButton(text=i18n.get("button-enter-custom-group"), callback_data="onboard_group_custom")
        ],
        [
            InlineKeyboardButton(text=i18n.get("button-skip"), callback_data="onboard_skip_group")
        ]
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.edit_text(
        i18n.get("onboard-group-title"),
        reply_markup=keyboard,
        parse_mode='Markdown'
    )


@router.callback_query(F.data.startswith("onboard_group_") & (F.data != "onboard_group_custom"))
async def handle_onboarding_group_select(callback: CallbackQuery, i18n: I18nContext):
    """Handle preset group selection during onboarding"""
    user_id = callback.from_user.id

    # Extract group code
    group_code = callback.data.replace("onboard_group_", "")

    # Set user group
    set_user_group(user_id, group_code)
    group_display = format_group_display(group_code)
    await callback.answer(i18n.get("feedback-group-set", group=group_display))

    # Show welcome complete message
    await show_onboarding_complete(callback.message, i18n)


@router.callback_query(F.data == "onboard_group_custom")
async def handle_onboarding_group_custom(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    """Prompt for custom group input during onboarding"""
    await state.set_state(OnboardingStates.waiting_for_group)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.get("button-skip"), callback_data="onboard_skip_group")]
    ])

    await callback.message.edit_text(
        i18n.get("onboard-group-custom"),
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()


@router.callback_query(F.data == "onboard_skip_group")
async def handle_onboarding_skip_group(callback: CallbackQuery, state: FSMContext, i18n: I18nContext):
    """Skip group selection during onboarding"""
    await state.clear()
    await callback.answer(i18n.get("feedback-skip-group"))

    # Show welcome complete message
    await show_onboarding_complete(callback.message, i18n)


async def show_onboarding_complete(message: Message, i18n: I18nContext):
    """Show onboarding complete message"""
    await message.edit_text(
        i18n.get("onboard-complete"),
        parse_mode='Markdown'
    )


@router.callback_query(F.data == "onboard_complete")
async def handle_onboarding_complete(callback: CallbackQuery, i18n: I18nContext):
    """Acknowledge onboarding complete"""
    await callback.answer(i18n.get("feedback-welcome"))
