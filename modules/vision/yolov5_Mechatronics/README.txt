Welcome to the creatively named yoloscript!

✅PREREQUISITES:
- Pip and Git installed
- A dataset to train
- execution of the script
  in its default directory

Directory Structure to expect:

<main folder>   - yoloscript.sh
                - README.txt (this)
		- scripts - image_resizer.py/organizer.sh/yaml_maker.sh
		- Insert_Data_Here - images/labels
		- Output_Data_Here - images/labels - test/train/valid
                - yolov5        - datasets
                                - models	- requirements.txt
                                		- yolov5m.yaml
                                	

Usage was made to be as simple as possible. All that is required of the user is to dump their dataset into the appropriately titled folder 
"Insert_Date_Here"'s images and labels folder respectively. if for some reason the folders are missing, they should be automatically created
upon running the script for the first time so you don't have to live with the fear that you are making folders where they don't belong. Once
you are sure everything is in place, you should be good to go to run the script itself.

To execute the script, make sure that you are in the same directory as the script 'yoloscript.sh' and you will have to provide at least 3
arguments. The arguments in question are the number of epochs, the weight, and however many classes that you have. Execution is as follows:

- bash yoloscript.sh <# of epochs> "<weighting>" "<object #1>" "<object #2 (etc.)>"
- If you aren't using any weighting, just enter empty quotes: ""
- yoloscript will take any number of classes/objects greater than 0

For example: "bash yoloscript.sh 10 "" shark" is a valid use of the script (minus the quotations before bash and after shark of course)


FAQ:

A. I got "AttributeError: module 'importlib_metadata' has no attribute 'EntryPoints'" what's the big idea?

Q. This may come as a result of a version conflict with the importlib_metadata package, a dependency of yolov5, 
    update it like so: pip install --upgrade importlib_metadata
