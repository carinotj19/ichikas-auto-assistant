"""
领取礼物
"""
import logging

from kotonebot import task, device, Loop, sleep
from kotonebot.errors import MissingResourceVariant

from . import R
from .common import go_home

logger = logging.getLogger(__name__)

@task('领取礼物', screenshot_mode='manual')
def gift():
    # 进入礼物界面
    go_home()
    logger.debug('Entering gift ui')
    for _ in Loop():
        if R.Hud.ButtonClaimAll.find():
            logger.info('Now at gift ui')
            break
        elif R.Daily.ButtonGift.try_click():
            logger.debug('Clicked gift button')
            sleep(0.5)
    # 领取礼物
    if R.Hud.ButtonClaimAll.q(colored=True).find():
        device.click()
        sleep(0.5)
        for _ in range(12):
            try:
                if R.CommonDialog.ButtonAwardClaimedOk.try_click():
                    logger.debug('Clicked award claimed ok button.')
                    sleep(0.5)
                    break
                if R.CommonDialog.TextAwardClaimedOk.find():
                    logger.debug('Waiting for award claimed dialog button.')
                    sleep(0.5)
                    continue
            except MissingResourceVariant:
                pass

            if R.Hud.ButtonClaimAll.find() and not R.Hud.ButtonClaimAll.q(colored=True).find():
                logger.debug('Gift claim button is no longer claimable.')
                break
            sleep(0.5)
    else:
        logger.info('No gift to claim')
    go_home()
