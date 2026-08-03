import time
import logging
from itertools import count

from kotonebot import color, device, task, Loop, sleep

from .. import R
from ..common import go_home
from ._common import enter_story, skip_stories

logger = logging.getLogger(__name__)

def _episode_point() -> tuple[int, int] | None:
    for scan in range(3):
        if scan:
            # The episode list may reopen at either end. Visit the top first,
            # then the bottom, so every episode is inspected from either state.
            y1, y2 = ((0.25, 0.75), (0.75, 0.25))[scan - 1]
            device.swipe_scaled(x1=0.75, y1=y1, x2=0.75, y2=y2)
            sleep(0.8)

        skipped = R.Story.BadgeSkippedEpisode.find_all()
        if skipped:
            marker = max(skipped, key=lambda obj: obj.rect.center.y)
            logger.info('Skipped episode found. Prioritizing it.')
            return R.Story.PointFirstEpisode.x, marker.rect.center.y + 40

        unread = color.find_all(
            '#ff5589',
            rect=R.Story.BoxEpisodeStatusColumn,
            threshold=0.98,
        )
        if unread:
            marker = max(unread, key=lambda result: result.position[1])
            logger.info('Unread episode found.')
            return R.Story.PointFirstEpisode.x, marker.position[1] + 35

    logger.info('No skipped or unread episode found after scanning the episode list.')
    return None

def _go_list():
    """
    前往主线剧情列表

    前置：-\n
    结束：主线剧情列表
    """
    go_home()
    for _ in Loop():
        if R.Story.ImageMainStory.try_click():
            sleep(1)
        elif R.Hud.ButtonStory.try_click():
            sleep(1)
        elif R.Story.StoryList.ButtonExpandUnit.find():
            break

def _filter_not_joined():
    """
    设置为只显示未参加虚拟演唱会的剧情

    前置：主线剧情列表
    结束：主线剧情列表，且已过滤未参加虚拟演唱会的剧情
    """
    for _ in Loop():
        # 等过滤弹窗展示
        if R.Story.StoryList.ButtonConfirmFilter.find():
            break
        # 打开过滤弹窗
        elif R.Story.StoryList.ButtonFilter.try_click():
            sleep(0.4)
    clicked = False
    for _ in Loop():
        if not clicked:
            device.click(R.Story.StoryList.PointFilterCategoryAll)
            device.click(R.Story.StoryList.PointFilterViewAll)
            device.click(R.Story.StoryList.PointFilterNotJoined)
            clicked = True
            sleep(0.3)
        # 确认过滤弹窗
        elif R.Story.StoryList.ButtonConfirmFilter.try_click():
            sleep(0.8)
        # 等弹窗关闭
        elif R.Story.StoryList.ButtonFilter.find():
            break

def _claim_after_show() -> bool:
    """Enter an unlocked After Show, wait for participation credit, then leave."""
    entered = False
    for _ in range(2):
        device.click(R.Story.PointAfterShow)
        deadline = time.monotonic() + 5
        transitioning = False
        for _ in Loop(interval=1):
            if R.Story.ButtonAfterShowExit.exists():
                entered = True
                break
            if not R.Story.ButtonBookmark.exists():
                if not transitioning:
                    transitioning = True
                    deadline = time.monotonic() + 120
            if time.monotonic() >= deadline:
                break
        if entered:
            break
        if transitioning:
            raise RuntimeError('After Show transition did not finish.')
    if not entered:
        logger.info('After Show is locked or unavailable.')
        return False

    logger.info('After Show loaded; waiting for participation credit.')
    sleep(22)
    deadline = time.monotonic() + 30
    last_exit_click: float | None = None
    for _ in Loop(interval=1):
        now = time.monotonic()
        if reward := R.Cm.TextAwardClaimed.find():
            x, y = reward.rect.center
            device.click(x + 80, y)
            logger.info('Dismissed After Show claimed rewards.')
            sleep(0.5)
            continue
        if R.Story.ButtonBookmark.exists() or R.Story.TextEventStory.exists():
            logger.info('After Show entered and exited.')
            return True
        if now >= deadline:
            device.click(R.Story.ButtonAfterShowExit.template.slice_rect.center)
            logger.warning('After Show exit is still pending; pressed Back to recover.')
            deadline = now + 3
            sleep(0.5)
            continue
        if (last_exit_click is None or now - last_exit_click >= 3) and R.Story.ButtonAfterShowExit.try_click():
            last_exit_click = now
            continue

def _farm_single() -> bool:
    """
    刷单个剧情

    前置：主线剧情列表，且已过滤未读剧情
    结束：主线剧情列表，且已过滤未读剧情
    """
    # 进入分集列表
    clicked = False
    for _ in Loop():
        if R.Story.StoryList.ButtonEnter.try_click():
            clicked = True
            sleep(1)
        elif clicked and R.Story.ButtonBookmark.exists():
            break
    # 已解锁的 After Show 可以直接参加；锁定时先补完剧情。
    joined = _claim_after_show()
    while not joined:
        episode_point = _episode_point()
        if episode_point is None:
            logger.info('No incomplete episode or joinable After Show; skipping this event.')
            break
        enter_story(episode_point=episode_point)
        def _end():
            # 处理 MV 播放（主线剧情）
            if R.Story.TextMvPausedDialog.exists():
                R.Story.ButtonSkipMv.try_click()
                return False
            return R.Story.ButtonBookmark.exists()
        skip_stories(
            mode='read',
            end_condition=_end
        )
        joined = _claim_after_show()
    # 返回列表
    for _ in Loop():
        if R.Story.StoryList.ButtonExpandUnit.find():
            break
        elif R.Story.ButtonGoBack.try_click():
            sleep(0.5)
    return joined

def _select_next():
    """
    选择下一个剧情

    前置：主线剧情列表
    结束：主线剧情列表
    """
    # 先等到返回列表页面
    R.Story.StoryList.ButtonExpandUnit.wait()
    # 再点下一个
    device.click(R.Story.StoryList.PointNext)
    sleep(0.2)

@task('刷剧情')
def farm_story():
    _go_list()
    _filter_not_joined()
    for i in count(1):
        start_time = time.time()
        logger.info(f'Farming story, starting {i}/∞.')
        joined = _farm_single()
        if joined:
            _filter_not_joined()
        else:
            _select_next()
        logger.info(f'Farming story, finished {i}/∞. Took {time.time() - start_time:.2f}s.')
