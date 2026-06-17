from typing import Literal
from typing_extensions import assert_never

import cv2
import numpy as np
from kotonebot import task, logging, Loop, device, sleep
from kotonebot.core import TemplateMatchPrefab
from kotonebot.backend import image

from . import R
from iaa.definitions.enums import ShopItem
from iaa.context import conf as get_conf, task_reporter, server
from iaa.game_ui.list_view import ListViewItem
from iaa.game_ui.side_tabbar import SideTabbar

logger = logging.getLogger(__name__)

WORLD_LINK_TAB_COUNT = 5
WORLD_LINK_TAB_OVERALL_X = 266
WORLD_LINK_TAB_STEP_X = 200
WORLD_LINK_TAB_SEARCH_RECT = (140, 65, 1140, 125)
WORLD_LINK_ACTIVE_HSV_LOWER = np.array((125, 45, 80), dtype=np.uint8)
WORLD_LINK_ACTIVE_HSV_UPPER = np.array((165, 255, 255), dtype=np.uint8)
WORLD_LINK_STRIP_HSV_LOWER = np.array((0, 0, 115), dtype=np.uint8)
WORLD_LINK_STRIP_HSV_UPPER = np.array((179, 75, 235), dtype=np.uint8)
WORLD_LINK_STRIP_MIN_RATIO = 0.50
WORLD_LINK_STRIP_MIN_EDGE_RATIO = 0.05
WORLD_LINK_TAB_Y_RATIO = 0.146

def _shop_item_to_resource(item: ShopItem) -> type[TemplateMatchPrefab]:
    match item:
        case ShopItem.ITEM_CRYSTAL:
            return R.Jp.Shop.Items.Crystal
        case ShopItem.ITEM_WISH_PIECE:
            return R.Jp.Shop.Items.WishPiece
        case ShopItem.ITEM_BONUS_ENERGY_DRINK_S:
            return R.Jp.Shop.Items.BonusEnergyDrinkS
        case ShopItem.ITEM_STAMP_VOUCHER:
            return R.Jp.Shop.Items.StampVoucher
        case ShopItem.ITEM_PRACTICE_SCORE_INTERMEDIATE:
            return R.Jp.Shop.Items.PracticeScoreIntermediate
        case ShopItem.ITEM_MUSIC_CARD:
            return R.Jp.Shop.Items.MusicCard
        case ShopItem.ITEM_MIRACLE_GEM:
            return R.Jp.Shop.Items.MiracleGem
        case ShopItem.ITEM_MAGIC_CLOTH:
            return R.Jp.Shop.Items.MagicCloth
        case ShopItem.ITEM_MAGIC_THREAD:
            return R.Jp.Shop.Items.MagicThread
        case ShopItem.ITEM_MAGICAL_SEED:
            return R.Jp.Shop.Items.MagicalSeed
        case ShopItem.ITEM_WISH_DROP:
            return R.Jp.Shop.Items.WishDrop
        case ShopItem.ITEM_COVER_CARD_VOUCHER:
            return R.Jp.Shop.Items.CoverCardVoucher
        case ShopItem.ITEM_COIN_100000:
            return R.Jp.Shop.Items.Coin100000
        case ShopItem.ITEM_COIN_1:
            return R.Jp.Shop.Items.Coin1
        case ShopItem.ITEM_SKILL_UP_SCORE_INTERMEDIATE:
            return R.Jp.Shop.Items.SkillUpScoreIntermediate
        case ShopItem.ITEM_3STAR_MEMBER | ShopItem.ITEM_2STAR_MEMBER:
            raise Exception('3Star and 2Star member items should be handled separately due to their variable icons')
        case _:
            assert_never(item)

def _match_item(item: ListViewItem, targets: list[ShopItem]) -> ShopItem | None:
    star_count = _is_char_item(item)
    if star_count is not None:
        if star_count == 2 and ShopItem.ITEM_2STAR_MEMBER in targets:
            return ShopItem.ITEM_2STAR_MEMBER
        elif star_count == 3 and ShopItem.ITEM_3STAR_MEMBER in targets:
            return ShopItem.ITEM_3STAR_MEMBER
        else:
            return None
    
    for target in targets:
        if target in (ShopItem.ITEM_3STAR_MEMBER, ShopItem.ITEM_2STAR_MEMBER):
            continue
        resource = _shop_item_to_resource(target)
        # 需要先处理缩放
        # 有时候 icon_image 会略小于模板，导致匹配失败
        icon_image = item.icon_image
        template = resource.template.pixels
        icon_height, icon_width = icon_image.shape[:2]
        template_height, template_width = template.shape[:2]
        if icon_height < template_height or icon_width < template_width:
            scale = max(template_width / icon_width, template_height / icon_height)
            icon_image = cv2.resize(icon_image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # ret = image.find(icon_image, template, threshold=0)
        # logger.debug("Match: %s confidence=%.2f", target.display(server()), ret.score if ret else -1)
        # cv2.imshow('icon_image', icon_image)
        # cv2.imshow('template', template)
        # cv2.waitKey(0)

        # 由于不同服务器右下角文本字体不一致，这里调低阈值
        if image.find(icon_image, template, threshold=0.5):
            return target
    return None

def _is_char_item(item: ListViewItem) -> Literal[2] | Literal[3] | None:
    """判断一个商品是否为角色卡片。

    :return: 若是，返回卡片星级，否则返回 None。
    """
    img = item.image
    # 首先根据 Lv1 文本判断是否为角色
    if not image.find(img, R.Shop.TextLv1.template):
        return None
    
    # 然后根据价格判断星级
    if image.find(img, R.Shop.Icon5000EventCoin.template):
        return 2
    elif image.find(img, R.Shop.Icon15000EventCoin.template):
        return 3
    else:
        logger.warning("Failed to determine character card star count for item %d", item.index)
        return None

def _find_world_link_tab_points(screenshot=None) -> list[tuple[int, int]]:
    img = device.screenshot() if screenshot is None else screenshot
    height, width = img.shape[:2]
    x1, y1, x2, y2 = WORLD_LINK_TAB_SEARCH_RECT
    x1 = max(0, min(width - 1, x1))
    x2 = max(x1 + 1, min(width, x2))
    y1 = max(0, min(height - 1, y1))
    y2 = max(y1 + 1, min(height, y2))

    roi = img[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, WORLD_LINK_ACTIVE_HSV_LOWER, WORLD_LINK_ACTIVE_HSV_UPPER)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), dtype=np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_rect: tuple[int, int, int, int] | None = None
    best_area = 0.0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if area < 1_000 or w < 120 or h < 18:
            continue
        if area > best_area:
            best_area = area
            best_rect = (x1 + x, y1 + y, w, h)

    if best_rect is not None:
        _, active_y, _, active_h = best_rect
        tab_y = active_y + active_h // 2
    else:
        strip_mask = cv2.inRange(hsv, WORLD_LINK_STRIP_HSV_LOWER, WORLD_LINK_STRIP_HSV_UPPER)
        strip_ratio = np.count_nonzero(strip_mask) / strip_mask.size
        edge_ratio = np.count_nonzero(cv2.Canny(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), 80, 180)) / strip_mask.size
        if strip_ratio < WORLD_LINK_STRIP_MIN_RATIO or edge_ratio < WORLD_LINK_STRIP_MIN_EDGE_RATIO:
            return []
        tab_y = int(round(height * WORLD_LINK_TAB_Y_RATIO))

    return [
        (WORLD_LINK_TAB_OVERALL_X + WORLD_LINK_TAB_STEP_X * index, tab_y)
        for index in range(WORLD_LINK_TAB_COUNT)
        if WORLD_LINK_TAB_OVERALL_X + WORLD_LINK_TAB_STEP_X * index < width
    ]

def goto_event_shop() -> None:
    """导航到活动商店界面
    
    前置：无\n
    结束：成功进入活动商店界面
    """
    for _ in Loop(interval=1):
        if R.Shop.TextEndTimeUntil.exists():
            if R.Shop.ButtonExchange.exists():
                device.click(1255, 25)
                logger.debug("Closed menu overlay on event shop")
                sleep(0.5)
                continue
            logger.info("Now at event shop")
            return
        elif R.Shop.ButtonExchange.try_click():
            logger.debug("Clicked on Exchange button")
        elif R.Shop.ButtonEventExchange.try_click():
            logger.debug("Clicked on Event Exchange button")
        elif R.Login.ButtonMenu.try_click():
            logger.debug("Clicked on Menu button")

def _purchase(item: ListViewItem):
    assert item.price_rect is not None

    # 首先打开购买对话框
    for _ in Loop():
        if R.Shop.AmountDialog.ButtonConfirm.exists():
            logger.info("Purchase dialog opened")
            break
        else:
            device.click(item.price_rect.center)
            sleep(0.5)
    
    # 调整大小
    plus_btn = R.Shop.AmountDialog.ButtonPlus.find()
    if plus_btn is None and R.Shop.AmountDialog.ButtonConfirm.exists():
        # 说明是卡片，不需要调整数量
        pass
    else:
        # 否则调整到最大
        assert plus_btn is not None
        for _ in Loop(interval=0.5):
            if R.Shop.AmountDialog.ButtonPlus.q(enabled=True).find():
                logger.debug("Purchase amount +10")
                for _ in range(10):
                    plus_btn.click()
                    sleep(0.2)
            else:
                logger.info("Purchase amount maximized")
                break
        
    # 确认购买
    # R.Shop.AmountDialog.ButtonCancel.click()
    # sleep(1)
    btn = R.Shop.AmountDialog.ButtonConfirm.wait()
    if not btn.enabled:
        if not btn.enabled:
            logger.info("Event coin not enough for purchasing. Skipping...")
            R.Shop.AmountDialog.ButtonCancel.click()
            sleep(0.5)
            return False
        logger.info("Event coin not enough for purchasing. Skipping...")
        return False
    for _ in Loop():
        if btn := R.Shop.AmountDialog.ButtonConfirm.find():
            btn.click()
            logger.info("Clicked confirm button")
            sleep(1)
        elif R.Shop.TextExchangeDone.try_click():
            sleep(0.5)
            logger.info("Purchase successful")
            return True

def _do_single() -> None:
    rep = task_reporter()
    targets = list(get_conf().event_shop.purchase_items)
    all_items = list(ShopItem)
    
    view = R.Shop.EventShopListView.require()
    assert view.scrollable is not None
    view.scrollable.measure_bounds()

    rep.message('扫描列表')
    view.scrollable.to_top()
    remaining = set(targets)
    available_targets: set[ShopItem] = set()
    for item in view.walk(reset_to_top=False):
        # 按 remaining 更高效，但是为了调试方便，按 all_items 来
        # matched_item = _match_item(item, list(remaining))
        matched_item = _match_item(item, all_items)
        if matched_item is None:
            logger.warning("Item %d does not match any target", item.index)
            continue
        logger.debug("Matched item %s", matched_item.display(server()))
        available_targets.add(matched_item)
        remaining.discard(matched_item)
        # if not remaining:
        #     break
    purchasable_targets = [target for target in targets if target in available_targets]

    for target in targets:
        if target not in available_targets:
            logger.info("Target item %s not found in event shop. Skipping.", target.display(server()))

    if not purchasable_targets:
        logger.info("No configured target items found in event shop.")
        return

    with rep.phase('购买商品', total=len(purchasable_targets)) as phase:
        for target in purchasable_targets:
            phase.step(target.display(server()))
            view.scrollable.to_top()

            for item in view.walk(reset_to_top=False):
                matched_item = _match_item(item, [target])
                if matched_item != target:
                    continue

                logger.info("Found target item %s", target.display(server()))
                if _purchase(item):
                    # 购买后商品列表会变化，并且界面会自动回顶；
                    # 当前 walk() 的滚动与坐标上下文都已失效，必须整轮重扫。
                    break

                logger.info("Skipping target item %s because it cannot be purchased now", target.display(server()))
                break

def _do_current_event_shop() -> None:
    world_link_tab_points = _find_world_link_tab_points()
    if not world_link_tab_points:
        _do_single()
        return

    logger.info("World Link event shop tabs found: %d", len(world_link_tab_points))
    for index, point in enumerate(world_link_tab_points, start=1):
        logger.info("Processing World Link shop tab %d/%d", index, len(world_link_tab_points))
        device.click(point)
        sleep(0.8)
        _do_single()

@task('活动商店', screenshot_mode='manual')
def event_shop():
    goto_event_shop()

    rep = task_reporter()
    sidebar = SideTabbar()
    tabs = sidebar.update().tabs
    if len(tabs) == 0:
        logger.warning("No tabs found in sidebar. Continuing without switching tabs.")
        _do_current_event_shop()
        return
        
    with rep.phase('活动', total=len(tabs)):
        for tab in tabs:
            sidebar.switch_to(tab)
            _do_current_event_shop()
