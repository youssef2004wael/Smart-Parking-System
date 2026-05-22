import numpy as np
from ultralytics.trackers.byte_tracker import BYTETracker
from ultralytics.utils import IterableSimpleNamespace
class _FakeTrack:
    def __init__(self, tlbr, track_id, score, cls):
        self.tlbr = tlbr
        self.track_id = track_id
        self.score = score
        self.cls = cls
        self.is_activated = True

class PerCameraTracker:
    def __init__(self):
        args = IterableSimpleNamespace(
            track_high_thresh=0.5,
            track_low_thresh=0.1,
            new_track_thresh=0.6,
            track_buffer=30,
            match_thresh=0.8,
            gating_thresh=0.2,
            mot20=False,
            fuse_score=False,
            with_reid=False,
            proximity_thresh=0.5,
            appearance_thresh=0.25,
        )
        self.tracker = BYTETracker(args=args, frame_rate=30)

    def update(self, detections, frame):
        if len(detections) == 0:
            return []

        class DetectionWrapper:
            def __init__(self, dets):
                self.data = dets
                self.xyxy = dets[:, :4]
                self.conf = dets[:, 4]
                self.cls = dets[:, 5]

                x1, y1, x2, y2 = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3]
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                w = x2 - x1
                h = y2 - y1
                self.xywh = np.stack([cx, cy, w, h], axis=1)

            def __getitem__(self, idx):
                return DetectionWrapper(self.data[idx])

            def __len__(self):
                return len(self.data)

        wrapped = DetectionWrapper(detections)
        raw_tracks = self.tracker.update(wrapped, frame)

        # ✅ newer ultralytics returns ndarray of shape (N, 7): [x1,y1,x2,y2,id,conf,cls]
        # older returns list of STrack objects — handle both
        if isinstance(raw_tracks, np.ndarray):
            return self._wrap_ndarray_tracks(raw_tracks)
        return raw_tracks  # already STrack list

    def _wrap_ndarray_tracks(self, arr):
        """Wrap numpy rows into objects that mimic STrack interface."""
        tracks = []
        for row in arr:
            x1, y1, x2, y2, track_id, conf, cls = row[:7]
            tracks.append(_FakeTrack(
                tlbr=(x1, y1, x2, y2),
                track_id=int(track_id),
                score=float(conf),
                cls=int(cls)
            ))
        return tracks