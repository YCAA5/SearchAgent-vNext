import customtkinter as ctk
import pytest


@pytest.fixture(scope='session')
def tk_root():
    window = ctk.CTk()
    window.withdraw()
    yield window
    window.destroy()
