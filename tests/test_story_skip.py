import unittest
from unittest import mock

from iaa.tasks import common as task_common
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


class GoHomeTests(unittest.TestCase):
    def test_go_home_skips_an_active_story_reader(self) -> None:
        resources = mock.Mock()
        resources.Hud.ButtonLive.find.side_effect = [False, False, False, True]
        resources.Hud.ButtonGoBack.try_click.return_value = False
        resources.Story.ButtonSkipStory.try_click.side_effect = [False, False, True]
        resources.Story.ButtonIconSkip.try_click.side_effect = [False, True]
        resources.Story.ButtonStoryMenu.try_click.return_value = True
        fake_device = mock.Mock()

        with mock.patch.dict(
            task_common.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 4,
                'device': fake_device,
                'server': lambda: 'en',
                'task_reporter': mock.Mock(return_value=mock.Mock()),
            },
        ):
            task_common.go_home()

        resources.Story.ButtonStoryMenu.try_click.assert_called_once()
        self.assertEqual(resources.Story.ButtonIconSkip.try_click.call_count, 2)
        self.assertEqual(resources.Story.ButtonSkipStory.try_click.call_count, 3)
        fake_device.click.assert_not_called()


class MainStoryTests(unittest.TestCase):
    def test_claim_after_show_enters_and_exits_when_unlocked(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.return_value = True
        resources.Story.ButtonAfterShowExit.try_click.side_effect = [True, False]
        resources.Story.ButtonBookmark.exists.side_effect = [False, True]
        resources.Story.TextEventStory.exists.return_value = False
        resources.Cm.TextAwardClaimed.find.return_value = None
        fake_device = mock.Mock()
        wait = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': fake_device,
                'sleep': wait,
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertTrue(claimed)
        self.assertEqual(
            fake_device.click.call_args_list,
            [
                mock.call(resources.Story.PointAfterShow),
            ],
        )
        resources.Story.ButtonAfterShowExit.try_click.assert_called_once()
        wait.assert_called_once_with(22)

    def test_claim_after_show_waits_after_episode_page_starts_transitioning(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.side_effect = [False, False, False, True]
        resources.Story.ButtonAfterShowExit.try_click.return_value = True
        resources.Story.ButtonBookmark.exists.side_effect = [False, True, False, True]
        resources.Story.TextEventStory.exists.return_value = False
        resources.Cm.TextAwardClaimed.find.return_value = None
        fake_device = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': fake_device,
                'sleep': mock.Mock(),
                'time': mock.Mock(monotonic=mock.Mock(side_effect=[0, 1, 2, 80, 110, 111, 112, 113, 114])),
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertTrue(claimed)
        fake_device.click.assert_called_once_with(resources.Story.PointAfterShow)

    def test_claim_after_show_presses_back_until_episode_list_returns(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.return_value = True
        resources.Story.ButtonAfterShowExit.try_click.return_value = True
        resources.Story.ButtonAfterShowExit.template.slice_rect.center = (56, 53)
        resources.Story.ButtonBookmark.exists.return_value = False
        resources.Story.TextEventStory.exists.side_effect = [False, False, True]
        resources.Cm.TextAwardClaimed.find.return_value = None
        fake_device = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': fake_device,
                'sleep': mock.Mock(),
                'time': mock.Mock(monotonic=mock.Mock(side_effect=[0, 1, 2, 32, 33])),
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertTrue(claimed)
        resources.Story.ButtonAfterShowExit.try_click.assert_called_once()
        self.assertEqual(
            fake_device.click.call_args_list,
            [
                mock.call(resources.Story.PointAfterShow),
                mock.call((56, 53)),
            ],
        )

    def test_claim_after_show_retries_an_ignored_early_exit_click(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.return_value = True
        resources.Story.ButtonAfterShowExit.try_click.return_value = True
        resources.Story.ButtonBookmark.exists.side_effect = [False, False, False, True]
        resources.Story.TextEventStory.exists.return_value = False
        resources.Cm.TextAwardClaimed.find.return_value = None

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': mock.Mock(),
                'sleep': mock.Mock(),
                'time': mock.Mock(monotonic=mock.Mock(side_effect=[0, 1, 2, 3, 5, 6])),
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertTrue(claimed)
        self.assertEqual(resources.Story.ButtonAfterShowExit.try_click.call_count, 2)

    def test_claim_after_show_dismisses_claimed_rewards_after_exit(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.return_value = True
        resources.Story.ButtonAfterShowExit.try_click.return_value = True
        resources.Story.ButtonBookmark.exists.side_effect = [False, True]
        resources.Story.TextEventStory.exists.return_value = False
        reward = mock.Mock()
        reward.rect.center = (634, 419)
        resources.Cm.TextAwardClaimed.find.side_effect = [None, reward, None]
        fake_device = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': fake_device,
                'sleep': mock.Mock(),
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertTrue(claimed)
        self.assertEqual(
            fake_device.click.call_args_list,
            [
                mock.call(resources.Story.PointAfterShow),
                mock.call(714, 419),
            ],
        )
        resources.Story.ButtonAfterShowExit.try_click.assert_called_once()

    def test_claim_after_show_accepts_episode_list_at_timeout_boundary(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.return_value = True
        resources.Story.ButtonAfterShowExit.try_click.return_value = True
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.TextEventStory.exists.return_value = False
        resources.Cm.TextAwardClaimed.find.return_value = None

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': mock.Mock(),
                'sleep': mock.Mock(),
                'time': mock.Mock(monotonic=mock.Mock(side_effect=[0, 1, 32])),
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertTrue(claimed)
        resources.Story.ButtonAfterShowExit.try_click.assert_not_called()

    def test_claim_after_show_accepts_event_story_tab_as_episode_list(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.return_value = True
        resources.Story.ButtonBookmark.exists.return_value = False
        resources.Story.TextEventStory.exists.return_value = True
        resources.Cm.TextAwardClaimed.find.return_value = None

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': mock.Mock(),
                'sleep': mock.Mock(),
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertTrue(claimed)
        resources.Story.ButtonAfterShowExit.try_click.assert_not_called()

    def test_claim_after_show_skips_locked_or_missing_card(self) -> None:
        resources = mock.Mock()
        resources.Story.ButtonAfterShowExit.exists.return_value = False
        resources.Story.ButtonBookmark.exists.return_value = True
        fake_device = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': fake_device,
                'sleep': mock.Mock(),
            },
        ):
            claimed = main_story._claim_after_show()

        self.assertFalse(claimed)
        self.assertEqual(
            fake_device.click.call_args_list,
            [
                mock.call(resources.Story.PointAfterShow),
                mock.call(resources.Story.PointAfterShow),
            ],
        )

    def test_filter_not_joined_selects_all_views_and_unjoined_shows(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonConfirmFilter.find.side_effect = [False, True]
        resources.Story.StoryList.ButtonFilter.try_click.return_value = True
        resources.Story.StoryList.ButtonConfirmFilter.try_click.side_effect = [True, False]
        resources.Story.StoryList.ButtonFilter.find.return_value = True
        fake_device = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                'device': fake_device,
                'sleep': mock.Mock(),
            },
        ):
            main_story._filter_not_joined()

        self.assertEqual(
            fake_device.click.call_args_list,
            [
                mock.call(resources.Story.StoryList.PointFilterCategoryAll),
                mock.call(resources.Story.StoryList.PointFilterViewAll),
                mock.call(resources.Story.StoryList.PointFilterNotJoined),
            ],
        )

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

        self.assertEqual(point, (874, 310))
        find_all.assert_called_once_with(
            '#ff5589',
            rect=status_column,
            threshold=0.98,
        )

    def test_episode_point_scrolls_to_top_for_offscreen_skipped_episode(self) -> None:
        resources = mock.Mock()
        resources.Story.PointFirstEpisode.x = 874
        skipped = mock.Mock()
        skipped.rect.center.y = 592
        resources.Story.BadgeSkippedEpisode.find_all.side_effect = [[], [skipped]]
        fake_device = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'color': mock.Mock(find_all=mock.Mock(return_value=[])),
                'device': fake_device,
                'sleep': mock.Mock(),
            },
        ):
            point = main_story._episode_point()

        self.assertEqual(point, (874, 632))
        fake_device.swipe_scaled.assert_called_once_with(
            x1=0.75,
            y1=0.25,
            x2=0.75,
            y2=0.75,
        )

    def test_episode_point_checks_bottom_after_scanning_top(self) -> None:
        resources = mock.Mock()
        resources.Story.PointFirstEpisode.x = 874
        skipped = mock.Mock()
        skipped.rect.center.y = 192
        resources.Story.BadgeSkippedEpisode.find_all.side_effect = [[], [], [skipped]]
        fake_device = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'color': mock.Mock(find_all=mock.Mock(return_value=[])),
                'device': fake_device,
                'sleep': mock.Mock(),
            },
        ):
            point = main_story._episode_point()

        self.assertEqual(point, (874, 232))
        self.assertEqual(
            fake_device.swipe_scaled.call_args_list,
            [
                mock.call(x1=0.75, y1=0.25, x2=0.75, y2=0.75),
                mock.call(x1=0.75, y1=0.75, x2=0.75, y2=0.25),
            ],
        )

    def test_farm_single_retries_back_until_story_list_is_visible(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonEnter.try_click.side_effect = [True, False]
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.StoryList.ButtonExpandUnit.find.side_effect = [None, None, object()]
        resources.Story.ButtonGoBack.try_click.return_value = True
        enter_story = mock.Mock()
        claim_after_show = mock.Mock(side_effect=[False, True])

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                '_episode_point': mock.Mock(return_value=(874, 333)),
                '_claim_after_show': claim_after_show,
                'enter_story': enter_story,
                'skip_stories': mock.Mock(),
                'sleep': mock.Mock(),
            },
        ):
            main_story._farm_single()

        enter_story.assert_called_once_with(episode_point=(874, 333))
        self.assertEqual(claim_after_show.call_count, 2)
        self.assertEqual(resources.Story.ButtonGoBack.try_click.call_count, 2)

    def test_farm_single_ignores_stale_episode_list_before_select_click(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonEnter.try_click.side_effect = [False, True, False]
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.StoryList.ButtonExpandUnit.find.return_value = object()
        enter_story = mock.Mock()
        claim_after_show = mock.Mock(side_effect=[False, True])

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                '_episode_point': mock.Mock(return_value=(874, 333)),
                '_claim_after_show': claim_after_show,
                'enter_story': enter_story,
                'skip_stories': mock.Mock(),
                'sleep': mock.Mock(),
            },
        ):
            main_story._farm_single()

        self.assertEqual(resources.Story.StoryList.ButtonEnter.try_click.call_count, 3)
        resources.Story.ButtonBookmark.exists.assert_called_once()
        enter_story.assert_called_once_with(episode_point=(874, 333))
        self.assertEqual(claim_after_show.call_count, 2)

    def test_farm_single_joins_unlocked_after_show_without_replaying_episode(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonEnter.try_click.side_effect = [True, False]
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.StoryList.ButtonExpandUnit.find.return_value = object()
        enter_story = mock.Mock()
        skip_stories = mock.Mock()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                '_claim_after_show': mock.Mock(return_value=True),
                'enter_story': enter_story,
                'skip_stories': skip_stories,
                'sleep': mock.Mock(),
            },
        ):
            main_story._farm_single()

        enter_story.assert_not_called()
        skip_stories.assert_not_called()

    def test_farm_single_reads_until_after_show_unlocks(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonEnter.try_click.side_effect = [True, False]
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.StoryList.ButtonExpandUnit.find.return_value = object()
        enter_story = mock.Mock()
        skip_stories = mock.Mock()
        claim_after_show = mock.Mock(side_effect=[False, False, True])

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                '_episode_point': mock.Mock(side_effect=[(874, 333), (874, 433)]),
                '_claim_after_show': claim_after_show,
                'enter_story': enter_story,
                'skip_stories': skip_stories,
                'sleep': mock.Mock(),
            },
        ):
            joined = main_story._farm_single()

        self.assertTrue(joined)
        self.assertEqual(
            enter_story.call_args_list,
            [
                mock.call(episode_point=(874, 333)),
                mock.call(episode_point=(874, 433)),
            ],
        )
        self.assertEqual(skip_stories.call_count, 2)

    def test_farm_single_skips_event_without_after_show(self) -> None:
        resources = mock.Mock()
        resources.Story.StoryList.ButtonEnter.try_click.side_effect = [True, False]
        resources.Story.ButtonBookmark.exists.return_value = True
        resources.Story.StoryList.ButtonExpandUnit.find.return_value = object()

        with mock.patch.dict(
            main_story.__dict__,
            {
                'R': resources,
                'Loop': lambda *args, **kwargs: [None] * 5,
                '_episode_point': mock.Mock(return_value=None),
                '_claim_after_show': mock.Mock(return_value=False),
                'enter_story': mock.Mock(),
                'skip_stories': mock.Mock(),
                'sleep': mock.Mock(),
            },
        ):
            joined = main_story._farm_single()

        self.assertFalse(joined)


if __name__ == '__main__':
    unittest.main()
