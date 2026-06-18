import unittest
import json
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QCoreApplication

from iaa.application.qt.controllers.run_controller import RunController
from iaa.application.service.scheduler import SchedulerService
from iaa.config.base import IaaConfig
from iaa.application.qt.models.mappings import SERVER_DISPLAY_MAP, SERVER_VALUE_MAP
from iaa.config.schemas import GameConfig
from iaa.definitions.consts import bundle_id_by_server, package_by_server
from iaa.definitions.enums import ShopItem
from iaa.tasks.registry import (
    is_task_supported,
    task_support_reason,
    task_support_status,
)


def make_iaa_config(server: str = 'en') -> IaaConfig:
    return IaaConfig.model_validate(
        {
            'version': 1,
            'name': 'test',
            'description': 'test',
            'game': {
                'server': server,
            },
            'live': {},
        }
    )


class GlobalEnConfigTests(unittest.TestCase):
    def test_game_config_accepts_en_server(self) -> None:
        conf = GameConfig(server='en')

        self.assertEqual(conf.server, 'en')

    def test_global_package_and_bundle_mapping(self) -> None:
        self.assertEqual(package_by_server('en'), 'com.sega.ColorfulStage.en')
        self.assertEqual(bundle_id_by_server('en'), 'com.sega.ColorfulStage.en')

    def test_global_server_is_exposed_to_settings_options(self) -> None:
        self.assertIn('en', SERVER_DISPLAY_MAP)
        self.assertEqual(SERVER_VALUE_MAP[SERVER_DISPLAY_MAP['en']], 'en')

    def test_shop_item_display_accepts_en_server(self) -> None:
        self.assertEqual(ShopItem.ITEM_CRYSTAL.display('en'), 'crystal')
        self.assertEqual(ShopItem.from_display('en', '3star_event_card'), ShopItem.ITEM_3STAR_MEMBER)

    def test_global_en_task_support_policy_is_conservative(self) -> None:
        self.assertEqual(task_support_status('main_story', 'en'), 'candidate')
        self.assertTrue(is_task_supported('main_story', 'en'))
        self.assertEqual(task_support_status('gift', 'en'), 'candidate')
        self.assertEqual(task_support_status('event_shop', 'en'), 'unsupported')
        self.assertIn('尚未完成候选测试', task_support_reason('event_shop', 'en') or '')

    def test_non_global_servers_keep_existing_task_support(self) -> None:
        self.assertEqual(task_support_status('event_shop', 'jp'), 'supported')
        self.assertTrue(is_task_supported('event_shop', 'jp'))

    def test_global_en_regular_scheduler_filters_unsupported_tasks(self) -> None:
        conf = make_iaa_config('en')
        scheduler = SchedulerService(SimpleNamespace(config=SimpleNamespace(conf=conf)))

        task_ids = [task_id for task_id, _ in scheduler._get_enabled_tasks()]

        self.assertIn('start_game', task_ids)
        self.assertIn('solo_live', task_ids)
        self.assertIn('activity_story', task_ids)
        self.assertIn('cm', task_ids)
        self.assertIn('area_convos', task_ids)
        self.assertIn('gift', task_ids)
        self.assertNotIn('challenge_live', task_ids)
        self.assertNotIn('event_shop', task_ids)

    def test_global_en_manual_run_rejects_unsupported_task_before_starting(self) -> None:
        conf = make_iaa_config('en')
        scheduler = SchedulerService(SimpleNamespace(config=SimpleNamespace(conf=conf)))

        with self.assertRaisesRegex(ValueError, 'event shop|活动商店|not supported'):
            scheduler.run_single('event_shop', run_in_thread=False)

    def test_global_en_gui_marks_unsupported_tasks_not_runnable(self) -> None:
        QCoreApplication.instance() or QCoreApplication([])
        conf = make_iaa_config('en')
        scheduler = SimpleNamespace(
            running=False,
            is_starting=False,
            is_stopping=False,
            current_task_id='',
            current_task_name='',
            run_single=Mock(),
        )
        controller = RunController(
            SimpleNamespace(config=SimpleNamespace(conf=conf, save=Mock()), scheduler=scheduler),
            progress_bridge=Mock(),
            scrcpy_controller=SimpleNamespace(sync_visibility=Mock()),
        )
        controller._timer.stop()

        tasks = {item['id']: item for item in json.loads(controller.tasksStateJson())}

        self.assertTrue(tasks['main_story']['runnable'])
        self.assertEqual(tasks['main_story']['supportStatus'], 'candidate')
        self.assertFalse(tasks['event_shop']['runnable'])
        self.assertEqual(tasks['event_shop']['supportStatus'], 'unsupported')
        self.assertIn('尚未完成候选测试', tasks['event_shop']['supportReason'])


if __name__ == '__main__':
    unittest.main()
