import unittest
from unittest import mock

from iaa.tasks.story import _common
from iaa.tasks.story import main_story


class StorySkipTests(unittest.TestCase):
    def test_read_mode_dismisses_reward_before_finishing(self) -> None:
        state = {'award': False, 'dismissed': False}
        resources = mock.Mock()
        resources.Story.ButtonStoryMenu.try_click.return_value = False
        resources.CommonDialog.TextAwardClaimedOk.find.side_effect = (
            lambda: state['award'] and not state['dismissed']
        )
        resources.CommonDialog.ButtonAwardClaimedOk.try_click.side_effect = (
            lambda: state.update(dismissed=True) or True
        )
        fake_device = mock.Mock()
        fake_device.click_center.side_effect = lambda: state.update(award=True)

        with mock.patch.dict(
            _common.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': fake_device,
                'sleep': mock.Mock(),
            },
        ):
            _common.skip_stories(
                mode='read',
                end_condition=lambda: state['award'],
            )

        self.assertTrue(state['dismissed'])
        resources.CommonDialog.ButtonAwardClaimedOk.try_click.assert_called_once()


class MainStoryTests(unittest.TestCase):
    def test_episode_point_prioritizes_lowest_skipped_episode(self) -> None:
        resources = mock.Mock()
        resources.Story.PointFirstEpisode.x = 874
        upper_skip = mock.Mock()
        upper_skip.rect.center.y = 193
        lower_skip = mock.Mock()
        lower_skip.rect.center.y = 293
        resources.Story.BadgeSkippedEpisode.find_all.return_value = [
            upper_skip,
            lower_skip,
        ]
        find_all = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'color': mock.Mock(find_all=find_all),
            },
        ):
            point = main_story._episode_point()

        self.assertEqual(point, (874, 333))
        find_all.assert_not_called()

    def test_episode_point_falls_back_to_lowest_unread_episode(self) -> None:
        resources = mock.Mock()
        resources.Story.PointFirstEpisode.x = 874
        resources.Story.BadgeSkippedEpisode.find_all.return_value = []
        status_column = object()
        resources.Story.BoxEpisodeStatusColumn = status_column
        find_all = mock.Mock(
            return_value=[
                mock.Mock(position=(1178, 175)),
                mock.Mock(position=(1178, 275)),
            ],
        )

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'color': mock.Mock(find_all=find_all),
            },
        ):
            point = main_story._episode_point()

        self.assertEqual(point, (874, 315))
        find_all.assert_called_once_with(
            '#ff5589',
            rect=status_column,
            threshold=0.95,
        )

    def test_farm_single_retries_back_until_story_list_is_visible(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonEnter.try_click.side_effect = [True, False]
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.StoryList.ButtonExpandUnit.find.side_effect = [None, None, object()]
        resources.Story.ButtonGoBack.try_click.return_value = True
        enter_story = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                '_episode_point': mock.Mock(return_value=(874, 333)),
                'enter_story': enter_story,
                'skip_stories': mock.Mock(),
                'sleep': mock.Mock(),
            },
        ):
            main_story._farm_single()

        enter_story.assert_called_once_with(episode_point=(874, 333))
        self.assertEqual(resources.Story.ButtonGoBack.try_click.call_count, 2)

    def test_farm_single_ignores_stale_episode_list_before_select_click(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonEnter.try_click.side_effect = [False, True, False]
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.StoryList.ButtonExpandUnit.find.return_value = object()
        enter_story = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                '_episode_point': mock.Mock(return_value=(874, 333)),
                'enter_story': enter_story,
                'skip_stories': mock.Mock(),
                'sleep': mock.Mock(),
            },
        ):
            main_story._farm_single()

        self.assertEqual(resources.Story.StoryList.ButtonEnter.try_click.call_count, 3)
        resources.Story.ButtonBookmark.exists.assert_called_once()
        enter_story.assert_called_once_with(episode_point=(874, 333))


if __name__ == '__main__':
    unittest.main()
