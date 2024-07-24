import json
import math
from enum import Enum

S3_FRAMESIZE_BADGE_PATH = "https://static.drm.pbs.org/poc-4k-test/framesizebadges/"
S3_VIDEO_FILE_URI = "https://s3.amazonaws.com/pbs.moc-ingest/Hemingway_UHD_2398.mp4"
S3_CAPTION_FILE_URI = "https://s3.amazonaws.com/pbs.moc-ingest/Hemingway_UHD_2398.scc"
S3_OUTPUT_PATH = (
    "s3://pbs-videos-transcoded-ga-staging/poc-4k-test/outputs/test1/$fn$-cmaf"
)
S3_MULTICODEC_OUTPUT_PATH = "s3://pbs-video-dev/4k/multicodec/$fn$-multicodec"
S3_PBS_VIDEO_DEV_OUTPUT_PATH = "s3://pbs-video-dev/4k/"
MEDIACONVERT_ROLE_ARN = "arn:aws:iam::676581116332:role/MediaConvert_Default_Role"

# codecs = ["VP9", "HEVC", "AVC", "AV1"]
FRAMESIZES = [2160, 1440, 1080, 960, 720, 640, 432, 360, 234]

# framesize: (bitrate, max_bitrate)
vbr_bitrate_values = {
    2160: (20000000, 40000000),
    1440: (12000000, 14000000),
    1080: (8000000, 10000000),
    960: (5000000, 7000000),
    720: (2500000, 4500000),
    640: (1600000, 2400000),
    432: (900000, 1100000),
    360: (600000, 800000),
    234: (200000, 400000),
}


class Codec(Enum):
    VP9 = "VP9"
    HEVC = "HEVC"
    AVC = "AVC"
    AV1 = "AV1"


# The name MediaConvert uses as the "Codec:" field
class CodecAwsName(Enum):
    VP9 = "VP9"
    HEVC = "H_265"
    AVC = "H_264"
    AV1 = "AV1"


# output_groups = {
#     # "VP9": ("DASH ISO", "DASH_ISO_GROUP_SETTINGS"),
#     "VP9": ("CMAF", "CMAF_GROUP_SETTINGS"),
#     "HEVC": ("CMAF", "CMAF_GROUP_SETTINGS"),
#     "AVC": ("CMAF", "CMAF_GROUP_SETTINGS"),
#     "AV1": ("CMAF", "CMAF_GROUP_SETTINGS"),
# }


class RateControlMode(Enum):
    VP9 = "VBR"
    HEVC = "QVBR"
    AVC = "QVBR"
    AV1 = "QVBR"


class ContainerType(Enum):
    # VP9 = "MP4"
    VP9 = "CMFC"
    HEVC = "CMFC"
    AVC = "CMFC"
    AV1 = "CMFC"


def generate_image_insertion(codec: Codec, framesize):
    return {
        "ImageX": 0,
        "ImageY": 0,
        "Layer": 2,
        "ImageInserterInput": f"{S3_FRAMESIZE_BADGE_PATH}{Codec(codec).value.lower()}-{framesize}p.png",
        "Opacity": 50,
    }


def generate_codec_settings_blocks(codec: Codec, framesize):
    if codec == Codec.VP9:
        return {
            "Vp9Settings": {
                "RateControlMode": "VBR",
                "MaxBitrate": vbr_bitrate_values[framesize][1],
                "Bitrate": vbr_bitrate_values[framesize][0],
            }
        }
    elif codec == Codec.HEVC:
        return {
            "H265Settings": {
                "MaxBitrate": vbr_bitrate_values[framesize][1],
                "RateControlMode": RateControlMode[Codec(codec).value].value,
                "QvbrSettings": {
                    "QvbrQualityLevel": 9,  # ? vary this value
                },
                "SceneChangeDetect": "TRANSITION_DETECTION",
            }
        }

    elif codec == Codec.AVC:
        return {
            "H264Settings": {
                "MaxBitrate": vbr_bitrate_values[framesize][1],
                "RateControlMode": RateControlMode[Codec(codec).value].value,
                "QvbrSettings": {
                    "QvbrQualityLevel": 9,  # ? vary this value
                },
                "SceneChangeDetect": "TRANSITION_DETECTION",
            }
        }
    elif codec == Codec.AV1:
        return {
            "Av1Settings": {
                "RateControlMode": RateControlMode[Codec(codec).value].value,
                "QvbrSettings": {
                    "QvbrQualityLevel": 9,  # ? vary this value
                },
                "MaxBitrate": vbr_bitrate_values[framesize][1],
            }
        }


def generate_video_outputs(codecs: list[Codec], framesizes=FRAMESIZES):
    video_outputs = []
    for codec in codecs:
        for framesize in framesizes:
            framewidth = math.floor(int(framesize / 9 * 16))
            frameheight = framesize

            video_outputs.append(
                {
                    "ContainerSettings": {
                        "Container": ContainerType[Codec(codec).value].value
                    },
                    "VideoDescription": {
                        "Width": framewidth,
                        "ScalingBehavior": "DEFAULT",
                        "Height": frameheight,
                        "VideoPreprocessors": {
                            "Deinterlacer": {
                                "Algorithm": "INTERPOLATE",
                                "Mode": "DEINTERLACE",
                                "Control": "NORMAL",
                            },
                            "ImageInserter": {
                                "InsertableImages": [
                                    generate_image_insertion(codec, framesize)
                                ]
                            },
                        },
                        "TimecodeInsertion": "DISABLED",
                        "AntiAlias": "ENABLED",
                        "Sharpness": 100,
                        "CodecSettings": {
                            "Codec": CodecAwsName[Codec(codec).value].value,
                            # add the result of codec_settings_block
                            **generate_codec_settings_blocks(codec, framesize),
                        },
                        "AfdSignaling": "NONE",
                        "DropFrameTimecode": "ENABLED",
                        "RespondToAfd": "NONE",
                        "ColorMetadata": "INSERT",
                    },
                    "NameModifier": f"-{Codec(codec).value.lower()}-{framesize}",
                }
            )

    return video_outputs


job_details = {
    "Queue": "arn:aws:mediaconvert:us-east-1:676581116332:queues/Accelerated",
    "UserMetadata": {},
    "Role": MEDIACONVERT_ROLE_ARN,
    "Settings": {
        "TimecodeConfig": {"Source": "ZEROBASED"},
        # ordered: VP9, HEVC, AVC, AV1
        "OutputGroups": [
            {
                "CustomName": "multi-codec",
                "Name": "CMAF",
                "Outputs": generate_video_outputs(
                    codecs=[Codec.VP9, Codec.HEVC, Codec.AVC, Codec.AV1],
                    framesizes=FRAMESIZES,
                ),
                "OutputGroupSettings": {
                    "Type": "CMAF_GROUP_SETTINGS",
                    "CmafGroupSettings": {
                        "TargetDurationCompatibilityMode": "SPEC_COMPLIANT",
                        "WriteDashManifest": "DISABLED",
                        "SegmentLength": 6,
                        "MinFinalSegmentLength": 2,
                        "Destination": S3_OUTPUT_PATH,
                        "DestinationSettings": {
                            "S3Settings": {
                                "AccessControl": {
                                    "CannedAcl": "BUCKET_OWNER_FULL_CONTROL"
                                },
                                "StorageClass": "STANDARD",
                            }
                        },
                        "FragmentLength": 2,
                        "SegmentControl": "SEGMENTED_FILES",
                        "ManifestDurationFormat": "FLOATING_POINT",
                        "CodecSpecification": "RFC_6381",
                    },
                },
            },
        ],
        "FollowSource": 1,
        "Inputs": [
            {
                "InputClippings": [
                    # ! DEBUG ONLY only process the first 30 seconds
                    {
                        "EndTimecode": "00:00:30:00",
                        "StartTimecode": "00:00:00:00",
                    }
                ],
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "DefaultSelection": "DEFAULT",
                        "AudioDurationCorrection": "AUTO",
                    }
                },
                "VideoSelector": {},
                "TimecodeSource": "ZEROBASED",
                "CaptionSelectors": {
                    "Captions Selector 1": {
                        "SourceSettings": {
                            "SourceType": "SCC",
                            "FileSourceSettings": {"SourceFile": S3_CAPTION_FILE_URI},
                        }
                    }
                },
                "FileInput": S3_VIDEO_FILE_URI,
            }
        ],
    },
    "BillingTagsSource": "JOB",
    "AccelerationSettings": {"Mode": "ENABLED"},
    "StatusUpdateInterval": "SECONDS_60",
    "Priority": 0,
}


# write the json dump to the static directory
with open(f"static/poc_4k_emc_job_template.json", "w") as f:
    f.write(json.dumps(job_details, indent=2))
