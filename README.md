
```
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# create an env.json file with your AWS credentials

# generate framesize badges to be burned over segments in MediaConvert
python generate_framesize_badges.py

# generate the MediaConvert job template for making a multi-codec CMAF HLS manifest
# edit the script to fit your use case

python generate_emc_4k_job.py
```