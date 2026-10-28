"""Download NEU-DET and convert it to YOLO format with a fixed train/val/test split.

The split matches the v1 baseline: 30 images per class are held out from the
original training set as the test split (seed 42), and the original validation
set is kept as val.

Usage:
    python scripts/prepare_neu_det.py [--output data/neu_yolo]
"""

import argparse
import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

CLASS_NAMES = [
    "crazing",
    "inclusion",
    "patches",
    "pitted_surface",
    "rolled-in_scale",
    "scratches",
]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
SEED = 42
TEST_PER_CLASS = 30
KAGGLE_DATASET = "kaustubhdikshit/neu-surface-defect-database"


def list_images(folder):
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def make_splits(source):
    rng = random.Random(SEED)
    splits = {"train": [], "val": [], "test": []}

    for class_name in CLASS_NAMES:
        train_images = list_images(source / "train" / "images" / class_name)
        val_images = list_images(source / "validation" / "images" / class_name)

        assert len(train_images) == 240, f"{class_name}: expected 240 train images"
        assert len(val_images) == 60, f"{class_name}: expected 60 val images"

        rng.shuffle(train_images)
        splits["test"].extend(train_images[:TEST_PER_CLASS])
        splits["train"].extend(train_images[TEST_PER_CLASS:])
        splits["val"].extend(val_images)

    return splits


def convert_xml_to_yolo(xml_path, image_path):
    root = ET.parse(xml_path).getroot()

    filename = root.findtext("filename")
    if filename and Path(filename).stem != image_path.stem:
        raise ValueError(f"Filename mismatch: {filename} vs {image_path.name}")

    size = root.find("size")
    if size is None:
        raise ValueError(f"Missing image size in {xml_path.name}")

    width = int(size.findtext("width"))
    height = int(size.findtext("height"))
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid dimensions in {xml_path.name}")

    lines = []
    for obj in root.findall("object"):
        class_name = obj.findtext("name")
        if class_name not in CLASS_TO_ID:
            raise ValueError(f"Unexpected class {class_name} in {xml_path.name}")

        box = obj.find("bndbox")
        if box is None:
            raise ValueError(f"Missing bounding box in {xml_path.name}")

        # Clamp coordinates to image boundaries
        xmin = max(0.0, min(float(box.findtext("xmin")), width))
        xmax = max(0.0, min(float(box.findtext("xmax")), width))
        ymin = max(0.0, min(float(box.findtext("ymin")), height))
        ymax = max(0.0, min(float(box.findtext("ymax")), height))

        if xmax <= xmin or ymax <= ymin:
            raise ValueError(f"Invalid box in {xml_path.name}")

        lines.append(
            f"{CLASS_TO_ID[class_name]} "
            f"{(xmin + xmax) / 2 / width:.6f} {(ymin + ymax) / 2 / height:.6f} "
            f"{(xmax - xmin) / width:.6f} {(ymax - ymin) / height:.6f}"
        )

    if not lines:
        raise ValueError(f"No objects found in {xml_path.name}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path("data/neu_yolo"))
    parser.add_argument("--source", type=Path, help="Existing NEU-DET folder (skips download)")
    args = parser.parse_args()

    if args.source:
        source = args.source
    else:
        import kagglehub
        source = Path(kagglehub.dataset_download(KAGGLE_DATASET)) / "NEU-DET"

    xml_by_stem = {}
    for xml_path in source.rglob("*.xml"):
        if xml_path.stem in xml_by_stem:
            raise ValueError(f"Duplicate XML annotation: {xml_path.stem}")
        xml_by_stem[xml_path.stem] = xml_path

    splits = make_splits(source)

    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)

    for split_name, images in splits.items():
        image_out = output / "images" / split_name
        label_out = output / "labels" / split_name
        image_out.mkdir(parents=True)
        label_out.mkdir(parents=True)

        for image_path in images:
            xml_path = xml_by_stem.get(image_path.stem)
            if xml_path is None:
                raise ValueError(f"Missing annotation for {image_path.name}")
            shutil.copy2(image_path, image_out / image_path.name)
            (label_out / f"{image_path.stem}.txt").write_text(
                convert_xml_to_yolo(xml_path, image_path)
            )

        print(f"{split_name}: {len(images)} images")

    names = "\n".join(f"  {i}: {name}" for i, name in enumerate(CLASS_NAMES))
    (output / "data.yaml").write_text(
        f"path: {output}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        f"names:\n{names}\n"
    )
    print(f"Dataset written to {output}")


if __name__ == "__main__":
    main()
