""" Multicast DNS Service Discovery for Python, v0.14-wmcbrine
    Copyright 2003 Paul Scott-Murphy, 2014 William McBrine

    This module provides a framework for the use of DNS Service Discovery
    using IP multicast.

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, write to the Free Software
    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301
    USA
"""

import random
from collections import deque
from typing import TYPE_CHECKING

from .._utils.time import current_time_millis, millis_to_seconds
from .answers import (
    MULTICAST_DELAY_RANDOM_INTERVAL,
    AnswerGroup,
    _AnswerWithAdditionalsType,
    construct_outgoing_multicast_answers,
)

if TYPE_CHECKING:
    from .._core import Zeroconf


class MulticastOutgoingQueue:
    """An outgoing queue used to aggregate multicast responses."""

    __slots__ = ("zc", "queue", "additional_delay", "aggregation_delay")

    def __init__(self, zeroconf: 'Zeroconf', additional_delay: int, max_aggregation_delay: int) -> None:
        self.zc = zeroconf
        self.queue: deque[AnswerGroup] = deque()
        # Additional delay is used to implement
        # Protect the network against excessive packet flooding
        # https://datatracker.ietf.org/doc/html/rfc6762#section-14
        self.additional_delay = additional_delay
        self.aggregation_delay = max_aggregation_delay

    def async_add(self, now: float, answers: _AnswerWithAdditionalsType) -> None:
        """Add a group of answers with additionals to the outgoing queue."""
        assert self.zc.loop is not None
        random_delay = random.randint(*MULTICAST_DELAY_RANDOM_INTERVAL) + self.additional_delay
        send_after = now + random_delay
        send_before = now + self.aggregation_delay + self.additional_delay
        if len(self.queue):
            # If we calculate a random delay for the send after time
            # that is less than the last group scheduled to go out,
            # we instead add the answers to the last group as this
            # allows aggregating additonal responses
            last_group = self.queue[-1]
            if send_after <= last_group.send_after:
                last_group.answers.update(answers)
                return
        else:
            self.zc.loop.call_later(millis_to_seconds(random_delay), self.async_ready)
        self.queue.append(AnswerGroup(send_after, send_before, answers))

    def _remove_answers_from_queue(self, answers: _AnswerWithAdditionalsType) -> None:
        """Remove a set of answers from the outgoing queue."""
        for pending in self.queue:
            for record in answers:
                pending.answers.pop(record, None)

    def async_ready(self) -> None:
        """Process anything in the queue that is ready."""
        assert self.zc.loop is not None
        now = current_time_millis()

        if len(self.queue) > 1 and self.queue[0].send_before > now:
            # There is more than one answer in the queue,
            # delay until we have to send it (first answer group reaches send_before)
            self.zc.loop.call_later(millis_to_seconds(self.queue[0].send_before - now), self.async_ready)
            return

        answers: _AnswerWithAdditionalsType = {}
        # Add all groups that can be sent now
        while len(self.queue) and self.queue[0].send_after <= now:
            answers.update(self.queue.popleft().answers)

        if len(self.queue):
            # If there are still groups in the queue that are not ready to send
            # be sure we schedule them to go out later
            self.zc.loop.call_later(millis_to_seconds(self.queue[0].send_after - now), self.async_ready)

        if answers:
            # If we have the same answer scheduled to go out, remove them
            self._remove_answers_from_queue(answers)
            self.zc.async_send(construct_outgoing_multicast_answers(answers))
