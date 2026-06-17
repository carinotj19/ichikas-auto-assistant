import unittest

import cv2
import numpy as np

from iaa.tasks.event_shop import _find_world_link_tab_points


class EventShopWorldLinkTests(unittest.TestCase):
    def test_world_link_tabs_detect_from_active_tab_bar(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(image, (166, 80), (366, 113), (162, 68, 151), -1)

        self.assertEqual(
            _find_world_link_tab_points(image),
            [(266, 97), (466, 97), (666, 97), (866, 97), (1066, 97)],
        )

    def test_normal_event_without_top_tabs_is_ignored(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)

        self.assertEqual(_find_world_link_tab_points(image), [])

    def test_world_link_tabs_detect_from_strip_when_active_tab_is_not_purple(self) -> None:
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.rectangle(image, (180, 86), (1238, 122), (190, 185, 190), -1)
        for index, label in enumerate(('Overall', 'Kanade', 'Ena', 'Mizuki', 'Mafuyu')):
            x = 245 + 200 * index
            cv2.circle(image, (x - 30, 103), 14, (75, 75, 90), 2, cv2.LINE_AA)
            cv2.putText(
                image,
                label,
                (x, 110),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (70, 70, 85),
                2,
                cv2.LINE_AA,
            )
            if index > 0:
                cv2.line(image, (205 + 200 * index, 88), (205 + 200 * index, 120), (115, 115, 130), 2)

        self.assertEqual(
            _find_world_link_tab_points(image),
            [(266, 105), (466, 105), (666, 105), (866, 105), (1066, 105)],
        )


if __name__ == '__main__':
    unittest.main()
