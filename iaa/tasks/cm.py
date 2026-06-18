import time

from kotonebot import logging
from kotonebot import device, task, Loop, action, sleep

from . import R
from .common import go_home
from iaa.definitions.consts import package_name
from iaa.context import conf as get_conf, task_reporter, server

logger = logging.getLogger(__name__)

def _sleep(sec: float, msg: str = '', interval: float = 1):
    """带有任务消息更新的 sleep。

    :param sec: 睡眠总时长，单位秒
    :param msg: 要显示的消息，其中可以包含一个 `%d` 来显示剩余秒数， defaults to ''
    :param interval: 检查间隔，单位秒， defaults to 1
    """
    rp = task_reporter()
    logger.debug(f'Sleeping for {sec} seconds.')
    start_time = time.time()
    while time.time() - start_time < sec:
        if msg:
            rp.message(msg % max(0, int(sec - (time.time() - start_time))))
        sleep(interval)

def _find_cm_award_claimed():
    if server() == 'en':
        award = R.Cm.TextAwardClaimed.q(colored=True).find()
    else:
        award = R.Cm.TextAwardClaimed.find()
    return award or R.Cm.TextApRecovered.find()

def _click_cm_play_button():
    if server() == 'en':
        if matches := R.Cm.ButtonPlayCm.find_all():
            ret = min(matches, key=lambda obj: obj.rect.y1)
            x, y = ret.rect.center
            device.click(x + 105, y)
            return True
        return False
    return R.Cm.ButtonPlayCm.try_click()

def _dismiss_cm_award_claimed():
    device.click(1000, 520)
    sleep(0.5)

def _try_click_cm_ad_button(prefab, *, threshold: float | None = None):
    try:
        if threshold is None:
            return prefab.try_click()
        return prefab.q(threshold=threshold).try_click()
    except Exception:
        logger.debug('CM ad button match failed.', exc_info=True)
        return False

def _click_cm_ad_corner_close():
    device.click(1255, 23)
    sleep(0.5)
    device.click(1230, 93)
    sleep(1)

@action('是否位于交叉路口')
def is_at_intersection() -> bool:
    # return AnyOf[
    #     R.Scene.Intersection.BuildingLogo,
    #     R.Scene.Intersection.IconCm
    # ].find(threshold=0.8) is not None
    return (
        R.Scene.Intersection.BuildingLogo.q(threshold=0.9).find() is not None or
        R.Scene.Intersection.IconCm.q(threshold=0.9).find() is not None
    )

@action('前往交叉路口', screenshot_mode='manual')
def go_intersection():
    """
    前置：位于首页\n
    结束：位于交叉路口
    """
    logger.info('Going to intersection.')
    device.screenshot()
    if is_at_intersection():
        logger.info('Now at intersection.')
        return
    # 打开地图
    for _ in Loop(interval=0.6):
        if R.Map.ButtonOpenMap.try_click():
            logger.debug('Clicked open map button.')
            sleep(0.5)
        elif R.Map.ButtonGoToReality.try_click():
            logger.info('Now at Sekai map. Changing to real world.')
            sleep(0.5)
        elif R.Map.ButtonGoToSekai.find():
            logger.debug('Now at real world map.')
            break
    # 进入交叉路口
    device.screenshot()
    swipe_count = 0
    MAX_SWIPE_COUNT = 5
    for _ in Loop(interval=0.6):
        if R.Map.Intersection.try_click():
            logger.debug('Clicked intersection on map.')
        elif is_at_intersection():
            logger.debug('Now at intersection.')
            break
        else:
            # 重置视图到右下角
            device.swipe_scaled(x1=0.7, x2=0.4, y1=0.5, y2=0.5)
            swipe_count += 1
            if swipe_count >= MAX_SWIPE_COUNT:
                logger.debug('Reached max swipe count but still not found. Stop.')
                return

@action('打开 CM 界面', screenshot_mode='manual')
def open_cm() -> bool:
    """
    前置：位于交叉路口\n
    结束：位于 CM 弹窗

    :returns: 是否成功打开 CM 界面。若为 False，原因是今天的广告都看完了。
    """
    logger.info('Opening CM.')
    swipe_count = 0
    MAX_SWIPE_COUNT = 5
    for _ in Loop(interval=0.6):
        if ret := R.Scene.Intersection.IconCm.q(threshold=0.6).find():
            # TODO: 改用 image.find 的 rect 参数重构
            x1, y1, x2, y2 = R.Cm.BoxCmIconDetectRect.xyxy
            x, y = ret.rect.center
            if x1 < x < x2 and y1 < y < y2:
                logger.debug('CM icon is in the detection area.')
                device.click(x, y)
                logger.debug('Clicked CM icon.')
                continue
            sleep(0.4)
        elif R.Cm.ButtonPlayCm.find():
            logger.debug('Now at CM.')
            return True
        
        # 向左滑
        device.swipe_scaled(x1=0.7, x2=0.4, y1=0.5, y2=0.5)
        logger.debug('Swiped left.')
        swipe_count += 1
        if swipe_count >= MAX_SWIPE_COUNT:
            logger.debug('Reached max swipe count but still not found. Stop.')
            return False
    return False

@action('看广告', screenshot_mode='manual')
def clear_common_cm():
    """
    前置：已经在 CM 弹窗\n
    结束：位于交叉路口
    """
    logger.info('Clearing CM.') 
    rep = task_reporter()
    d = device.of_android()
    state: int = 1 # 1=开始看，2=载入，3=正在看，4=等结果
    state_started_at = time.time()
    wait_sec = get_conf().cm.watch_ad_wait_sec
    for _ in Loop(interval=0.6):
        if state == 1:
            # 开始看
            if R.Cm.TextCmFailed.find():
                logger.info('Ad play failed.')
                device.click(1, 1)
                sleep(0.5)
            elif _find_cm_award_claimed():
                logger.info('Ad award claimed.')
                _dismiss_cm_award_claimed()
                rep.message('奖励已领取')
            elif R.Cm.ButtonCmStart.q(threshold=0.7).try_click():
                logger.debug('Clicked 視聴開始 button.')
                sleep(1)
                state = 2
                state_started_at = time.time()
            elif _click_cm_play_button():
                rep.message('播放广告')
                logger.debug('Clicked CM start button.')
                sleep(1)
                state = 2
                state_started_at = time.time()
            # 没有剩余广告了
            else:
                if is_at_intersection():
                    logger.info('All ads cleared.')
                    break
                elif R.Hud.ButtonGoBack.exists():
                    logger.info('All ads cleared.')
                    R.Hud.ButtonGoBack.try_click()
                    sleep(0.5)
                    break
                else:
                    logger.info('CM page is not visible. Assuming ad loaded.')
                    state = 3
                    state_started_at = time.time()
        elif state == 2:
            if R.Cm.TextCmFailed.find():
                logger.info('Ad play failed before ad loaded.')
                device.click(1, 1)
                sleep(0.5)
                state = 1
                state_started_at = time.time()
            elif _find_cm_award_claimed():
                logger.info('Ad award claimed before ad loaded.')
                _dismiss_cm_award_claimed()
                rep.message('å¥–åŠ±å·²é¢†å–')
                state = 1
                state_started_at = time.time()
            elif R.Cm.ButtonPlayCm.q(threshold=0.7).find():
                if time.time() - state_started_at < 8:
                    rep.message('等待广告载入')
                    logger.debug('Loading ad...')
                    sleep(0.2)
                else:
                    logger.info('Returned to CM selection before ad loaded.')
                    state = 1
                    state_started_at = time.time()
            else:
                rep.message('等待广告结束')
                logger.info(f'Ad loaded. Wait {wait_sec} sec.')
                state = 3
                state_started_at = time.time()
        elif state == 3:
            _sleep(wait_sec, msg='等待广告结束，剩余 %d 秒')
            logger.debug('Wait ad finished.')
            # 返回桌面再重新打开游戏就可以关闭广告
            if _try_click_cm_ad_button(R.Cm.Ad1.ButtonSkip, threshold=0.7):
                logger.debug('Clicked skip button after ad wait.')
                sleep(1)
            elif _try_click_cm_ad_button(R.Cm.Ad1.ButtonClose):
                logger.debug('Clicked close button after ad wait.')
                sleep(1)
            else:
                _click_cm_ad_corner_close()
                if device.commands.current_package() != package_name():
                    d.commands.adb_shell('input keyevent KEYCODE_HOME')
                    sleep(0.5)
                    d.launch_app(package_name())
                    sleep(0.5)
                logger.debug('Ad skipped.')
            state = 4
            state_started_at = time.time()
        elif state == 4:
            # 由于广告没放完就点了跳过导致领取奖励失败
            if R.Cm.TextCmFailed.find():
                logger.info('Ad play failed due to early skip.')
                device.click(1, 1) # 关闭弹窗
                sleep(0.5)
                state = 1
                state_started_at = time.time()
            # 看完了
            elif _find_cm_award_claimed():
                logger.info('Ad award claimed.')
                _dismiss_cm_award_claimed()
                rep.message('奖励已领取')
                state = 1
                state_started_at = time.time()
            # Applovin 广告特判
            elif _try_click_cm_ad_button(R.Cm.Ad1.ButtonClose):
                logger.info('Close button clicked. (Applovin/GP ad?)')
                sleep(1)
                state = 1
                state_started_at = time.time()
            elif _try_click_cm_ad_button(R.Cm.Ad1.ButtonSkip, threshold=0.7):
                logger.info('Skip button clicked. (Applovin/GP ad?)')
                sleep(1)
            # GooglePlay App 广告特判：
            # 点击 skip 按钮后会自动跳转到商店页面，需要跳过回来
            elif device.commands.current_package() != package_name():
                logger.info('Returning to game from ad. (GP ad?)')
                # device.commands.launch_app(package_name())
                # 有些广告，调用 launch_app 会触发重新播放，导致无限循环
                device.commands.adb_shell('am force-stop com.android.vending')
                device.commands.launch_app(package_name())
                sleep(1)
            elif R.Cm.ButtonPlayCm.q(threshold=0.7).find():
                logger.info('Returned to CM selection without result.')
                sleep(2)
                if _find_cm_award_claimed():
                    logger.info('Delayed ad award claimed.')
                    _dismiss_cm_award_claimed()
                    rep.message('奖励已领取')
                state = 1
                state_started_at = time.time()
            elif R.Hud.ButtonGoBack.exists():
                logger.info('Returned to in-game non-CM page. Going back.')
                R.Hud.ButtonGoBack.try_click()
                sleep(1)
                state = 1
                state_started_at = time.time()
            elif not R.Hud.ButtonGoBack.exists():
                logger.info('Trying top-right ad close button.')
                _click_cm_ad_corner_close()
            # 还在加载
            else:
                rep.message('等待结果')
                logger.debug('Waiting for result...')

@task('看广告', screenshot_mode='manual')
def cm():
    """
    看广告并领取奖励。包括演出积分/心愿结晶、活动货币、两次 AP 恢复、两次礼物、水晶、音乐商店。
    """
    if server() == 'cn':
        logger.info('CM task is not supported on CN server.')
        return
    go_home()
    rep = task_reporter()
    rep.message('正在前往交叉路口')
    go_intersection()
    rep.message('正在打开 CM 界面')
    if open_cm():
        clear_common_cm()
    else:
        logger.info('No ads available.')
