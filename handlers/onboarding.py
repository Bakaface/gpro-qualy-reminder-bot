"""Onboarding flow for new users"""
import logging
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from notifications import set_user_language, set_user_ui_language, set_user_group, LANGUAGE_OPTIONS
from utils import format_group_display
from .states import OnboardingStates
from .callbacks import build_language_keyboard
from . import router

logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("onboard_ui_lang_"))
async def handle_onboarding_ui_language_select(callback: CallbackQuery):
    """Handle bot UI language selection at start of onboarding"""
    user_id = callback.from_user.id

    # Extract language code (en or ru)
    ui_lang = callback.data.replace("onboard_ui_lang_", "")

    # Set UI language
    if set_user_ui_language(user_id, ui_lang):
        logger.info(f"User {user_id} selected UI language: {ui_lang}")

    # Now show GPRO language selection (existing flow)
    keyboard = build_language_keyboard(page=1, current_lang='gb', onboarding=True)

    # Use appropriate text based on selected UI language
    if ui_lang == 'ru':
        text = (
            "👋 **Добро пожаловать в GPRO Bot!**\n\n"
            "Теперь выберите предпочитаемый язык для ссылок на GPRO:\n\n"
            "🌍 **Выберите язык** (или пропустите для английского):"
        )
    else:
        text = (
            "👋 **Welcome to GPRO Bot!**\n\n"
            "Now choose your preferred language for GPRO race links:\n\n"
            "🌍 **Select your language** (or skip to use English):"
        )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')
    await callback.answer()


@router.callback_query(F.data.startswith("onboard_lang_page_"))
async def handle_onboarding_language_page(callback: CallbackQuery):
    """Handle language pagination during onboarding"""
    try:
        page = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Invalid page", show_alert=True)
        return

    keyboard = build_language_keyboard(page=page, current_lang='gb', onboarding=True)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("onboard_lang_") & ~F.data.in_(["onboard_lang_page_1", "onboard_lang_page_2", "onboard_lang_page_3", "onboard_lang_page_4"]))
async def handle_onboarding_language_select(callback: CallbackQuery):
    """Handle language selection during onboarding"""
    user_id = callback.from_user.id

    # Extract language code
    lang_code = callback.data.replace("onboard_lang_", "")

    # Set user language
    if set_user_language(user_id, lang_code):
        lang_display = LANGUAGE_OPTIONS.get(lang_code, lang_code)
        await callback.answer(f"✅ Language set to {lang_display}")
    else:
        await callback.answer("❌ Invalid language", show_alert=True)
        return

    # Proceed to group selection
    await show_onboarding_group_menu(callback.message, user_id)


@router.callback_query(F.data == "onboard_skip_lang")
async def handle_onboarding_skip_language(callback: CallbackQuery):
    """Skip language selection during onboarding"""
    user_id = callback.from_user.id
    await callback.answer("⏭️ Using default language (English)")

    # Proceed to group selection
    await show_onboarding_group_menu(callback.message, user_id)


async def show_onboarding_group_menu(message: Message, user_id: int):
    """Show group selection menu during onboarding"""
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="Elite", callback_data="onboard_group_E"),
            InlineKeyboardButton(text="Master 3", callback_data="onboard_group_M3")
        ],
        [
            InlineKeyboardButton(text="Pro 15", callback_data="onboard_group_P15"),
            InlineKeyboardButton(text="Amateur 42", callback_data="onboard_group_A42")
        ],
        [
            InlineKeyboardButton(text="Rookie 11", callback_data="onboard_group_R11")
        ],
        [
            InlineKeyboardButton(text="✏️ Enter Custom Group", callback_data="onboard_group_custom")
        ],
        [
            InlineKeyboardButton(text="⏭️ Skip", callback_data="onboard_skip_group")
        ]
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.edit_text(
        "🏁 **Group Selection**\n\n"
        "Choose your GPRO group to get personalized race links:\n\n"
        "Select a common group or enter your own:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )


@router.callback_query(F.data.startswith("onboard_group_") & (F.data != "onboard_group_custom"))
async def handle_onboarding_group_select(callback: CallbackQuery):
    """Handle preset group selection during onboarding"""
    user_id = callback.from_user.id

    # Extract group code
    group_code = callback.data.replace("onboard_group_", "")

    # Set user group
    set_user_group(user_id, group_code)
    group_display = format_group_display(group_code)
    await callback.answer(f"✅ Group set to {group_display}")

    # Show welcome complete message
    await show_onboarding_complete(callback.message)


@router.callback_query(F.data == "onboard_group_custom")
async def handle_onboarding_group_custom(callback: CallbackQuery, state: FSMContext):
    """Prompt for custom group input during onboarding"""
    await state.set_state(OnboardingStates.waiting_for_group)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Skip", callback_data="onboard_skip_group")]
    ])

    await callback.message.edit_text(
        "🏁 **Custom Group**\n\n"
        "Enter your group in one of these formats:\n"
        "• **E** (Elite)\n"
        "• **M3** (Master 3) - Master has groups 1-5\n"
        "• **P15** (Pro 15)\n"
        "• **A42** (Amateur 42)\n"
        "• **R11** (Rookie 11)\n\n"
        "Numbers can be 1-3 digits.",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await callback.answer()


@router.callback_query(F.data == "onboard_skip_group")
async def handle_onboarding_skip_group(callback: CallbackQuery, state: FSMContext):
    """Skip group selection during onboarding"""
    await state.clear()
    await callback.answer("⏭️ Skipped group selection")

    # Show welcome complete message
    await show_onboarding_complete(callback.message)


async def show_onboarding_complete(message: Message):
    """Show onboarding complete message"""
    await message.edit_text(
        "✅ **Setup Complete!**\n\n"
        "🏁 **GPRO Bot is ready!**\n\n"
        "**Available commands:**\n"
        "/status - Next race\n"
        "/calendar - Full season\n"
        "/next - Next season\n"
        "/settings - Preferences\n\n"
        "💡 *You can change these settings anytime using /settings*",
        parse_mode='Markdown'
    )


@router.callback_query(F.data == "onboard_complete")
async def handle_onboarding_complete(callback: CallbackQuery):
    """Acknowledge onboarding complete"""
    await callback.answer("✅ Welcome aboard!")
