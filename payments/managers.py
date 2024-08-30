from django.db import models


class MovementManager(models.Manager):
    def get_next_grouping_id(self):
        lastest_movement = self.order_by("created_at").last()
        if lastest_movement is None:
            return 0

        prev_grouping_id = lastest_movement.grouping_id
        return prev_grouping_id + 1
