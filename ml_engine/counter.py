import cv2
import torch
import supervision as sv
from transformers import DetrImageProcessor, DetrForObjectDetection
from PIL import Image
import numpy as np
from tqdm import tqdm
from core.config import settings

class CowCounterEngine:
    def __init__(self):
        print("🧠 Loading AI Models...")
        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")
            
        print(f"   [+] Compute Device: {self.device}")
        
        self.processor = DetrImageProcessor.from_pretrained(settings.MODEL_NAME)
        self.model = DetrForObjectDetection.from_pretrained(settings.MODEL_NAME)
        self.model.to(self.device)
        self.model.eval()
        
        self.allowed_labels = ['bird', 'sheep', 'cow', 'bear', 'dog', 'horse', 'zebra']

    # ADDED: progress_callback argument
    def process_video(self, source_path, target_path, progress_callback=None):
        video_info = sv.VideoInfo.from_video_path(source_path)
        print(f"   [+] Video Resolution: {video_info.width}x{video_info.height}")
        
        tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=30,
            minimum_matching_threshold=0.8,
            frame_rate=video_info.fps
        )
        
        line_zone = sv.LineZone(
            start=sv.Point(0, video_info.height // 2), 
            end=sv.Point(video_info.width, video_info.height // 2)
        )
        
        box_annotator = sv.BoxAnnotator(thickness=2, color=sv.ColorPalette.DEFAULT)
        label_annotator = sv.LabelAnnotator(text_scale=0.5, text_padding=5)
        trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=50)
        line_annotator = sv.LineZoneAnnotator(thickness=2, text_thickness=2, text_scale=1)

        frame_generator = sv.get_video_frames_generator(source_path)
        
        print("   [+] Starting Inference Loop...")
        
        total_frames = video_info.total_frames
        
        with sv.VideoSink(target_path, video_info=video_info) as sink:
            for i, frame in enumerate(tqdm(frame_generator, total=total_frames, unit="frame")):
                
                # --- PROGRESS REPORTING ---
                # Report every 5% or at least every 30 frames to avoid spamming Azure
                if progress_callback and (i % 30 == 0):
                    percent = round((i / total_frames) * 100)
                    progress_callback(percent)

                # A. Inference
                img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                inputs = self.processor(images=img_pil, return_tensors="pt").to(self.device)
                
                with torch.no_grad():
                    outputs = self.model(**inputs)

                target_sizes = torch.tensor([img_pil.size[::-1]]).to(self.device)
                results = self.processor.post_process_object_detection(
                    outputs, target_sizes=target_sizes, threshold=0.4
                )[0]

                # B. Parsing
                detections = sv.Detections.from_transformers(transformers_results=results)

                # C. Filtering
                valid_indices = []
                for idx, class_id in enumerate(detections.class_id):
                    class_name = self.model.config.id2label[class_id]
                    if class_name in self.allowed_labels:
                        valid_indices.append(idx)
                
                if valid_indices:
                    detections = detections[np.array(valid_indices)]
                    detections = detections[detections.area > 4000] 
                else:
                    detections = sv.Detections.empty()

                # D. Tracking & Counting
                detections = tracker.update_with_detections(detections)
                line_zone.trigger(detections=detections)

                # E. Annotation
                labels = [f"Cow #{id}" for id in detections.tracker_id]
                
                frame = trace_annotator.annotate(frame, detections)
                frame = box_annotator.annotate(frame, detections)
                frame = label_annotator.annotate(frame, detections, labels)
                frame = line_annotator.annotate(frame, line_counter=line_zone)
                
                sink.write_frame(frame)

        print("   [+] Processing Finished.")
        return {
            "total_in": int(line_zone.in_count),
            "total_out": int(line_zone.out_count),
            "total_count": int(line_zone.in_count + line_zone.out_count)
        }