# Third-Party Software and Data Notices

This file is an inventory aid, not legal advice. Verify the exact license text
shipped with every installed package, model weight, container component, and
dataset before redistribution or service deployment.

## Material runtime components

| Component | Recorded licensing information | Project action |
| --- | --- | --- |
| Ultralytics YOLO | AGPL-3.0 open-source option or a separate Enterprise license | Review AGPL obligations for code, trained weights, distribution, and network use before release or commercial deployment |
| PyTorch | See the license distributed with the pinned wheel/source release | Preserve notices and verify the exact release artifact |
| OpenCV 4.5+ | Apache License 2.0 | Preserve required notices |
| OpenSlide and official bindings | GNU LGPL 2.1 | Preserve license/source obligations for distributed binaries |
| NVIDIA CUDA base image | NVIDIA container and CUDA terms | Review before redistribution |
| FastAPI, Pydantic, NumPy, FPDF2, Roboflow client | See each pinned distribution’s metadata and bundled license | Generate and review a release SBOM/notices bundle |

Official references:

- [Ultralytics licensing](https://docs.ultralytics.com/#yolo-licenses-how-is-ultralytics-yolo-licensed)
- [OpenCV licensing](https://opencv.org/license/)
- [OpenSlide downloads and license](https://openslide.org/download/)

The root Apache-2.0 file covers original repository code only. It does not
replace third-party licenses and must not be presented as the sole license for a
container, checkpoint, or complete deployed system.

## Dataset licensing

No source dataset is approved for redistribution until `config/dataset_sources.yaml`
contains a verified license identifier and provenance status. A public download
page or API access does not by itself establish redistribution or derivative-
model rights.

## Release checklist

Before the next checkpoint release:

1. Resolve every dataset license and citation.
2. Record the license applicable to the base model and fine-tuned checkpoint.
3. Generate an SBOM for the container and Python environment.
4. Include third-party notices and corresponding source offers where required.
5. Obtain qualified legal review for any commercial or hosted deployment.
