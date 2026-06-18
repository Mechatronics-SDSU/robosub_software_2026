# Mechatronics_Vision

## Outline
- Date Created: 05/24/2026
- Contributors:
    - Noael Jabrael (GitHub: **JabraelNoael**, Discord: **mantiswhale**)
    - Gabriel Sean Gonsalves (GitHub: **GabrielSean-13**, Discord: **seaniiiiii**)
- Dependencies:
    - w.i.p.

Everything on this branch is for the purpose of the AUV's vision, this process is split into two sections being pre-deployment and deployment:

<u>pre-deployment</u>:
1. Producing Synthetic Data
    1. How to modify & annotate the classes that are being detected
2. Augmenting the data (on training side applies augmentations randomly per epoch)
3. Training the model
4. Evaluating the model

<u>deployment</u>:
1. ZED returns depth matrix, # of columns matches x pixels and # of rows matches y pixels, cell inputs are for z (distance)
2. DBSCAN is ran on the depth matrix to detect potential objects, these coordinates are transformed to the x,y coordinates of the original capture to crop the areas of the image that are most likely to be an object. The parameters for DBSCAN are listed below:
    1. minPTS (`min_samples`) : minimum number of neighboring points within `eps` radius required for a point to be considered a core point — higher values demand denser clusters and reduce noise sensitivity
    2. eps : neighborhood radius in metres — points within this distance of each other are treated as neighbors; larger values merge more points into the same cluster
    3. depth_downsample_step : stride applied when sampling the depth matrix before feeding it into DBSCAN — e.g. a value of `4` samples every 4th pixel, significantly cutting compute cost at the expense of fine spatial resolution
    4. wall_filter : custom post-DBSCAN filter; discards any cluster whose median depth falls outside a configured min/max range, removing large flat returns from walls, the floor, and the ceiling that would otherwise dominate the cluster output
    5. drop_clusters_less_than : custom post-DBSCAN filter; removes any cluster below a minimum point count after the algorithm runs, clearing out residual noise clusters that technically satisfied `eps` and `minPTS` but are too sparse to plausibly represent a real detectable object
3. YOLO is then deployed on the cropped feed from the previous step, this returns a dictionary of all the objects detected in the following formatting:
```python
{'obj1': ['ambulance', 1, 0.74, 0.2, 0.15, 5],
'obj2': ['fire', 2, 0.97, 0.3, 0.4, 11]}
```
Fields: `[class_label, class_id, conf, x_norm, y_norm, depth_m]`

- `class_label` : such as ambulance, fire, firetruck, blood
- `class_id` : corresponding id for `class_label` (irrelevant to you)
- `conf` : confidence the model is seeing the right thing
- `x_norm` : 0 = far-left,  1 = far-right
- `y_norm` : 0 = bottom,    1 = top
- `depth_m` : Euclidean distance to box center in metres (-1 if unavailable)
4. Video is saved during delpoyment as `.svo` formatting which allows for video AND depth parameter tweaking (video for YOLO and depth for DBSCAN). Note that the depth information isn't saved from the initial run but rather recalculated on the ZEDBox from `.svo` data

## Important Directories
### `~/blender_enviorment`
- `/HDRIs`
> High Dynamic Range Image (HDRI) downloaded from Polyhaven that are randomly cycled between to produce high quality and detailed backgrounds for the data generation

### `~/data`
- `/images`
> All of our training data (produced from `underwater_dataset_gen.py`)

- `/labels`
> Identically named files as `/images` but extension shift (.png $\to$ .txt), captures vertex coordinates that outline object's geometry. $(\text{class-id}, x_0, y_0, x_1, y_1, ..., x_n, y_n)$

- `/labels_bbox`
> Automatically computed using $L_\infty$ normalization from `/labels`. Acts as typical bounding box $(\text{class-id}, \text{x-center}\in [0,1], \text{y-center}\in [0,1], \text{width}, \text{height})$ annotation to pair with instance-segmented annotations

### `~/models`
> Contains sub-dirs for specific training cycles, each sub-dir has it's own evaluation metrics as graphs, `args.yaml` for the training parameters used, and `/weights` folder to store `.pt` files (pre-trained model weights)

### `~/recordings`
> Footage capturing: can record with the following formats which can all be disabeled in `config.yaml`
> 1. `<video>.svo` : preferable; stores video and computes depth using the ZEDBox, allows for offsight DBSCAN and YOLO parameter tweaking
> 2. `<video>.mp4` : raw footage from tests
> 3. `<video>_annotated.mp4` : mp4 footage with overlayed annotations, can be 1:1 computed from `<video>.mp4` but works as a quick way to see what the model sees live without running YOLO seperately.

## Important Files
### `underwater_dataset_gen.py`
> This file exists as a duplicate to store/transfer via GitHub. Make sure this file stays updated with the Blender-sided script (Open the Blender environment, click the "Scripting" tab). Listed below is some functionality of the file, read the comments on the file directly for more detail.
> 1. Load in and identify target objects
> 2. Configure constants (random variable ranges, how many images to generate, enviornment preferences, etc.)
> 3. Generate images per object with completely randomly selected variables such as distance, rotation, tilt, lighting, and etc., runs can be seeded for reproducibility.

### `training_config.yaml`
> Single source of truth for all training-time settings. Covers data paths, `label_kind` toggle (`polygon`/`bbox`), `ft_model` per label kind, `CLASS_NAMES`, training hyperparameters (`image_size`, `ft_epochs`, `ft_batch`, `ft_patience`), SupCon and DINO section parameters, and the full `augmentation` probability table. Change a value here and it takes effect across `train.ipynb` and `augmentation_pipeline.ipynb` without touching either notebook.

### `augmentation_pipeline.ipynb`
> Offline augmentation pipeline run once to expand the dataset before training. Process: load source images and polygon labels → convert polygons to bounding boxes → apply a configurable Albumentations transform stack → write augmented images and labels to `data/`. Augmentations include: horizontal/vertical flip, random crop, affine skew, hue rotation, smooth color gradient tint, Gaussian blur, Gaussian noise, Sobel edge enhancement, channel dropout, and cutout patches. Each transform fires independently at its configured probability.

> The final cell exports the active augmentation probabilities back to the config file using a read-merge-write strategy — it loads the file first, patches only the keys it controls, and writes it back, leaving any values you've manually edited untouched. (Yes this is possible — it's a standard config merge pattern.)

### `train.ipynb`
> Contains all training and evaluation code, notebook is split up into headered seections for the following functionality
> 1. Loading in data from `~/data`'s `/images`, `/labels`, and `/labels_bbox`. This also applies a train-test-split which proportionally chooses 80% of data (configurable) to train on and leaves the rest to evaluate the model against.
> 2. Loads in `yolo11m-seg.pt` which is a model that was trained on the COCO dataset with ~20M parameters, we fine-tune from this to save time and have a baseline that's already efficient at recognizing shapes, lines, curves, and other low-level features. Afterwards we attach our own CNN head so it looks for our labels instead of the COCO dataset labels
> 3. Allows you to name a run (let's say `v1`), this will build the dir `~/models/v1` which will contain `args.yaml` to store the parameters used and a bunch of graphs evaluating your model. Additionally `~/models/v1/weights` will be built which will contain: `best.pt` (the model that performed the best), `last.pt` (the most recent training epoch; this also allows the use of the resume parameter to continue training if training crashes or gets interrutped), and weights per every 5 epochs i.e. epoch0.pt,, epoch5.pt, epoch10.pt, .... This can allow for evaluating what your model is actually learning on the feature level if you so wish.
> 4. Fine-tuning (not to be confused with resume training) allows to continue training from a desired initial `.pt` to tune the model and continue training using new parameters, new data, etc. if you're observing poor model performance with things like glare, generate a glare-dense dataset and fine-tune for ~5-30 epochs on heavy-glare images to improve model performance in that specific issue without having to entirely retrain a model.

### `config.yaml`
> Allows configuring the following parameters (should be tuned before running `main.py`)
> 1. source as in where the feed is coming in from (camera, ZED, webcam, etc. through the use of `webcam` with an index for OpenCV or `zed` to run zed deployment process)
> 2. recording settings such as if we should record and store mp4, annotated mp4, svo or any combination of them including what directory to save them in
> 3. model namely what pre-trained weights we're using
> 4. classes filter out labels that you do not want the model to look for, None defaults to show all
> 5. YOLO parameters
> 6. zed hardware-sided such as resolution or fps limitations on the camera
> 7. DBSCAN parameters 

### `main.py`
> Reads `config.yaml`, no code changes needed between runs, all behavior is config-sided. Supports two sources (`zed` for the full ZED + depth pipeline, `webcam` for laptop/USB testing with depth disabled). On each frame: runs YOLO inference and returns detections as a dict (see format in Outline section). Recording is handled by the `Recorder` class.

## Usage

### Adding / Replacing Classes in `underwater_dataset_gen.py`

> This script runs inside Blender (Scripting tab). All changes described here are in the script itself unless noted otherwise.

#### 1. <u>pre-deploy</u>

Every detectable class needs three things inside the `.blend` file:

| Blender element | Naming convention | Purpose |
| --- | --- | --- |
| Collection | Capital first letter — e.g. `Lamb` | Groups the class; the script shows/hides entire collections per render so only the active DOI appears in frame |
| Image object | Lowercase — e.g. `lamb` | The actual rendered mesh/image-plane the camera sees |
| Annotation mesh | Same name + `_IS` suffix — e.g. `lamb_IS` | Drives the YOLO polygon label (see §2 below); must share the same origin as the image object |

To add a lamb and remove the four existing classes, replace the `DOIS` list in the CONFIG section:

```python
DOIS = [
    {"collection": "Lamb", "image_obj": "lamb", "is_obj": "lamb_IS", "class_id": 0, "label": "lamb"},
]
```
Also update `CLASS_NAMES` in `training_config.yaml` and `config.yaml` to match. Class IDs must be consistent across both files.

#### 2. The `_IS` Annotation Mesh

`lamb_IS` is a **closed vertex outline** of the lamb placed directly over the image object in the Blender viewport. It is a separate mesh whose vertices trace the visible perimeter of the object — think of it as a hand-drawn silhouette polygon. The script walks the edge graph at render time, projects each vertex through the live camera matrix, and writes the result as a YOLO instance-segmentation label (`class_id x1 y1 x2 y2 ...`).

Rules for a clean `_IS` mesh:
- Every vertex must have **exactly 2 edges** (a closed loop — no branches, no dead ends)
- Share the same **origin point** as the image object so rotation and scale applied to the image object carry over to `_IS` automatically
- Vertices can be added/moved in Edit Mode; the order Blender stores them doesn't matter — the script resolves perimeter order by walking the edge graph

#### 3. Randomized Parameters

Each render draws fresh values from the ranges defined at the top of the script. Changing a range only requires editing the two-element tuple next to the constant name:

| Category | What's randomised |
| --- | --- |
| **Camera** | Distance from DOI, azimuth/elevation angle, focal length |
| **DOI** | Yaw / pitch / roll rotation, uniform scale |
| **Lighting** | Sun position (x/y offset, height) and strength |
| **Environment** | Volumetric water density + color, ocean IOR + roughness, ocean sim frame, HDRI selection |

`GEN_PER_DOI_RANGE` controls how many images are produced per class (e.g. `(1, 100)` generates images `0001` through `0100`). `RANDOM_SEED` is randomised on each run by default; set it to a fixed integer to make a run reproducible.

### (<u>deploy</u>)
1. modify `config.yaml`, read comments on file for further clarity
2. run `main.py`
3. `build_detections() -> dict` reading in outputs gives insight on what objects are detected where (x, y, and depth)

## Status
- Current status: **Complete**