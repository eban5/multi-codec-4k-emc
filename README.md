
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

**Resolutions and Codecs Used**

|Resolution|Codec|Profile|Level|
|----|---|---|---|
|416 x 234 	    |	AVC     | 	Main | 	1.3  |   
|768 x 432 	    |	AVC     | 	Main | 	3    | 
|1280 x 720 	|	AVC     | 	Main | 	3.1  |   
|1920 x 1080    |	AVC     | 	High | 	4    | 
|416 x 234 	    |	HEVC    | 	Main | 	2    | 
|768 x 432 	    |	HEVC    | 	Main | 	3    | 
|1280 x 720     |	HEVC    | 	Main | 	3.1  |   
|1920 x 1080    |	HEVC    | 	Main | 	4    | 
|2560 x 1440    |	HEVC    | 	Main | 	5    | 
|3840 x 2160    |	HEVC    | 	Main | 	5    | 