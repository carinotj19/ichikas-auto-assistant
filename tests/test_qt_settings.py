import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication

from iaa.application.qt.controllers.settings_controller import SettingsController
from iaa.config.base import IaaConfig
from iaa.config.shared import SharedConfig


def make_conf() -> IaaConfig:
    return IaaConfig.model_validate(
        {
            'version': 1,
            'name': 'test',
            'description': 'test',
            'game': {
                'server': 'jp',
                'link_account': 'google',
            },
            'device': {
                'lifecycle': {
                    'type': 'mumu_v5',
                    'instance_id': '42',
                    'check_and_start': False,
                },
                'control_impl': 'scrcpy',
                'scrcpy_virtual_display': True,
            },
            'live': {},
        }
    )


def make_config_service(conf: IaaConfig, *, save: Mock | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        conf=conf,
        save=save or Mock(),
        save_shared=Mock(),
        current_config_name='test',
        shared=SharedConfig(),
    )


def make_controller(conf: IaaConfig, *, save: Mock | None = None) -> SettingsController:
    return SettingsController(
        SimpleNamespace(
            config=make_config_service(conf, save=save),
            scheduler=SimpleNamespace(device=None, connect_device=Mock()),
        )
    )


def runtime_field(controller: SettingsController, field_id: str) -> dict:
    return json.loads(controller.getRuntime())['fieldMap'][field_id]


class SettingsControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        QCoreApplication.instance() or QCoreApplication([])

    def test_set_value_forces_tw_link_account_to_no(self) -> None:
        conf = make_conf()
        save = Mock()
        controller = make_controller(conf, save=save)

        controller.setValue('game.server', 'tw')

        self.assertEqual(conf.game.server, 'tw')
        self.assertEqual(conf.game.link_account, 'no')
        save.assert_not_called()

    @patch('kotonebot.client.host.Mumu12V5Host.list')
    def test_refresh_mumu_instances_preserves_existing_selection(self, list_mock: Mock) -> None:
        list_mock.return_value = [SimpleNamespace(id='42', name='Main'), SimpleNamespace(id='43', name='Alt')]
        conf = make_conf()
        controller = make_controller(conf)

        controller.triggerAction('device.mumuInstanceId', 'refresh')
        field = runtime_field(controller, 'device.mumuInstanceId')

        self.assertEqual(field['value'], '42')
        self.assertEqual(len(field['options']), 3)

    @patch('kotonebot.client.host.Mumu12V5Host.list')
    def test_refresh_mumu_instances_prefers_ui_selected_id(self, list_mock: Mock) -> None:
        list_mock.return_value = [SimpleNamespace(id='42', name='Main'), SimpleNamespace(id='43', name='Alt')]
        conf = make_conf()
        controller = make_controller(conf)

        controller.setValue('device.mumuInstanceId', '43')
        controller.triggerAction('device.mumuInstanceId', 'refresh')
        field = runtime_field(controller, 'device.mumuInstanceId')

        self.assertEqual(field['value'], '43')

    def test_runtime_exposes_saved_mumu_instance(self) -> None:
        conf = make_conf()
        controller = make_controller(conf)

        field = runtime_field(controller, 'device.mumuInstanceId')

        self.assertEqual(field['value'], '42')


if __name__ == '__main__':
    unittest.main()
