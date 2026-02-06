"""
Pub/Sub reader: reads raw JSON byte messages from a Pub/Sub subscription.
"""

import apache_beam as beam
from apache_beam.io import ReadFromPubSub


class ReadFromFeedbackPubSub(beam.PTransform):

    def __init__(self, subscription: str):
        super().__init__()
        self._subscription = subscription

    def expand(self, pbegin):
        return pbegin | "ReadPubSubMessages" >> ReadFromPubSub(
            subscription=self._subscription,
            with_attributes=False,
        )
