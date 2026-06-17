from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from kotonebot import Loop

from ._fragments import handle_data_download, handle_notification
from .common import hanlde_tip_dialog

def data_download(loop: 'Loop'):
    if handle_data_download():
        return
    elif hanlde_tip_dialog():
        return
    elif handle_notification():
        return
