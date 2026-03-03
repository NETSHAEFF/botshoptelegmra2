from aiogram.fsm.state import State, StatesGroup


class UserStates(StatesGroup):
    waiting_receipt = State()


class AdminStates(StatesGroup):
    add_name = State()
    add_price = State()
    add_description = State()
    add_photo = State()
    add_content = State()

    edit_name = State()
    edit_price = State()
    edit_description = State()
    edit_photo = State()
    edit_content = State()

    set_intro = State()
    set_intro_photo = State()
    set_manual_instructions = State()
    set_ozon_instructions = State()
    set_yandex_instructions = State()
    set_yoomoney_instructions = State()

    broadcast_message = State()
