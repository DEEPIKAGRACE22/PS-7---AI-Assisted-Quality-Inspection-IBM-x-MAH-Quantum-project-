"""Ultralytics detector training with the dataset config and names passed as arguments.

Example:
  python train_detector.py --config configs/msdd.yaml --model yolov8l.pt --name E1_yolov8l --hyp hyp.yaml
"""
import argparse
import yaml
from ultralytics import YOLO


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True, help='Ultralytics dataset yaml (replaces the missing mix_8cls.yaml)')
    p.add_argument('--model', default='yolov8l.pt')
    p.add_argument('--name', required=True, help='experiment name')
    p.add_argument('--project', default='runs/detect')
    p.add_argument('--epochs', type=int, default=80)
    p.add_argument('--imgsz', type=int, default=640)
    p.add_argument('--batch', type=int, default=16)
    p.add_argument('--device', default='0')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--hyp', default=None, help='optional yaml of extra Ultralytics train args (augmentation etc.)')
    a = p.parse_args()

    extra = yaml.safe_load(open(a.hyp)) if a.hyp else {}
    model = YOLO(a.model)
    model.train(data=a.config, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device,
                workers=a.workers, seed=a.seed, project=a.project, name=a.name, **extra)


if __name__ == '__main__':
    main()
