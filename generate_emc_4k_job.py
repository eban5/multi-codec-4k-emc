import json
import math
from datetime import datetime
from enum import Enum

with open("env.json") as config_file:
    config = json.load(config_file)

S3_FRAMESIZE_BADGE_PATH = config["S3_FRAMESIZE_BADGE_PATH"]
MEDIACONVERT_QUEUE_ARN = config["MEDIACONVERT_QUEUE_ARN"]
MEDIACONVERT_ROLE_ARN = config["MEDIACONVERT_ROLE_ARN"]
S3_DESTINATION_PATH = config["S3_DESTINATION_PATH"]
S3_VIDEO_FILE_URI = config["S3_VIDEO_FILE_URI"]
S3_CAPTION_FILE_URI = config["S3_CAPTION_FILE_URI"]

# ASCENDING_LADDER = False

# The list of framesizes to produce outputs for, ordered by preference
FRAMESIZES = [
    720,
    234,
    # 360,
    432,
    # 960,
    1080,
    1440,
    2160,
]

# if ASCENDING_LADDER:
#     FRAMESIZES.reverse()


jobs_to_generate = [
    {
        # ! temp filename hack to support playback on Chromecast
        "job_name": "Tst4k_AABR-AVC_{codecs}_{formatted_datetime}",
        "codecs_to_use": ["HEVC", "AVC"],
    },
    # {
    #     "job_name": "Tst4k_{codecs}_{formatted_datetime}",
    #     "codecs_to_use": [
    #         "VP9",
    #     ],
    # },
]


# an AI wrote this, and it seems correct to me. blame the machine.
def bps_to_human_readable(bps):
    if bps >= 1_000_000:
        # Convert to Megabits per second
        value = bps / 1_000_000
        unit = "Mbps"
    else:
        # Convert to Kilobits per second
        value = bps / 1000
        unit = "Kbps"

    # Format the result as a string with the appropriate suffix
    readable_str = f"{value:.2f} {unit}"

    return readable_str


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


def calculate_vp9_max_bitrate(target_bitrate: int) -> int:

    # https://developers.google.com/media/vp9/settings/vod
    return math.floor(target_bitrate * 1.45)


# framesize: (bitrate, max_bitrate)
vbr_bitrate_values = {
    2160: (9000000, 15000000),
    1440: (7500000, 11000000),
    1080: (4000000, 7500000),
    960: (5000000, 7000000),
    720: (2500000, 4500000),
    432: (900000, 1100000),
    360: (600000, 800000),
    234: (200000, 400000),
}


vp9_bitrate_values = {
    2160: (5000000, calculate_vp9_max_bitrate(5000000)),
    1440: (4096000, calculate_vp9_max_bitrate(4096000)),
    1080: (1124000, calculate_vp9_max_bitrate(1124000)),
    960: (1024000, calculate_vp9_max_bitrate(1024000)),
    720: (1024000, calculate_vp9_max_bitrate(1024000)),
    432: (900000, calculate_vp9_max_bitrate(900000)),
    360: (276000, calculate_vp9_max_bitrate(276000)),
    234: (180000, calculate_vp9_max_bitrate(180000)),
}


def create_s3_output_path(job_name: str):
    if not job_name:
        output_dir = "multicodec10"
    else:
        output_dir = job_name
    return f"s3://{S3_DESTINATION_PATH}{output_dir}/$fn$"


def generate_image_insertion(codec: Codec, framesize):
    return {
        "ImageInserter": {
            "InsertableImages": [
                {
                    "ImageX": 0,
                    "ImageY": 0,
                    "Layer": 2,
                    "ImageInserterInput": f"{S3_FRAMESIZE_BADGE_PATH}{Codec(codec).value.lower()}-{framesize}p.png",
                    "Opacity": 50,
                }
            ]
        },
    }


def generate_codec_settings_block(codec: Codec, framesize):
    if framesize < 720:
        qvbr_quality_level = 4
    elif framesize >= 720 and framesize <= 1080:
        qvbr_quality_level = 7
    elif framesize > 1080:
        qvbr_quality_level = 9

    max_bitrate = vbr_bitrate_values[framesize][1]

    if codec == Codec.VP9:
        return {
            "Vp9Settings": {
                "RateControlMode": "VBR",
                "MaxBitrate": math.floor(vbr_bitrate_values[framesize][1] / 2),
                "Bitrate": math.floor(vbr_bitrate_values[framesize][0] / 2),
                "QualityTuningLevel": "MULTI_PASS_HQ",
            }
        }
    elif codec == Codec.HEVC:
        max_bitrate_hevc = math.floor(max_bitrate / 2)
        return {
            "H265Settings": {
                "InterlaceMode": "PROGRESSIVE",
                "NumberReferenceFrames": 3,
                "GopClosedCadence": 1,
                "AlternateTransferFunctionSei": "DISABLED",
                "HrdBufferInitialFillPercentage": 90,
                "GopSize": 3,
                "Slices": 4 if framesize < 720 else 2,
                "GopBReference": "ENABLED",
                "HrdBufferSize": max_bitrate_hevc * 2,
                "MaxBitrate": max_bitrate_hevc,
                "SpatialAdaptiveQuantization": "ENABLED",
                "TemporalAdaptiveQuantization": "ENABLED",
                "FlickerAdaptiveQuantization": "ENABLED",
                "RateControlMode": "QVBR",
                "QvbrSettings": {
                    "QvbrQualityLevel": qvbr_quality_level,
                },
                "CodecProfile": "MAIN_MAIN",
                "Tiles": "ENABLED",
                "MinIInterval": 0,
                "AdaptiveQuantization": "HIGH",
                "CodecLevel": "AUTO" if framesize < 2160 else "LEVEL_5",
                "SceneChangeDetect": "ENABLED",
                "QualityTuningLevel": "MULTI_PASS_HQ",
                "UnregisteredSeiTimecode": "DISABLED",
                "GopSizeUnits": "SECONDS",
                "NumberBFramesBetweenReferenceFrames": 3,
                "TemporalIds": "DISABLED",
                "SampleAdaptiveOffsetFilterMode": "ADAPTIVE",
                "WriteMp4PackagingType": "HVC1",
                "DynamicSubGop": "ADAPTIVE",
            }
        }

    elif codec == Codec.AVC:
        avc_codec_profile = "MAIN" if framesize < 1080 else "HIGH"

        return {
            "H264Settings": {
                "InterlaceMode": "PROGRESSIVE",
                "NumberReferenceFrames": 3,
                "Syntax": "DEFAULT",
                "GopClosedCadence": 1,
                "HrdBufferInitialFillPercentage": 90,
                "GopSize": 3,
                "Slices": 4,
                "GopBReference": "ENABLED",
                "HrdBufferSize": max_bitrate * 2,
                "MaxBitrate": max_bitrate,
                "SpatialAdaptiveQuantization": "ENABLED",
                "TemporalAdaptiveQuantization": "ENABLED",
                "FlickerAdaptiveQuantization": "ENABLED",
                "EntropyEncoding": "CABAC",
                "RateControlMode": "QVBR",
                "QvbrSettings": {
                    "QvbrQualityLevel": qvbr_quality_level,
                },
                "CodecProfile": avc_codec_profile,
                "MinIInterval": 0,
                "AdaptiveQuantization": "HIGH",
                "CodecLevel": "AUTO",
                "FieldEncoding": "PAFF",
                "SceneChangeDetect": "ENABLED",
                "QualityTuningLevel": "MULTI_PASS_HQ",
                "UnregisteredSeiTimecode": "DISABLED",
                "GopSizeUnits": "SECONDS",
                "NumberBFramesBetweenReferenceFrames": 3,
                "RepeatPps": "DISABLED",
                "DynamicSubGop": "ADAPTIVE",
            }
        }
    elif codec == Codec.AV1:
        return {
            "Av1Settings": {
                "GopSize": 60,
                "NumberBFramesBetweenReferenceFrames": 15,
                "Slices": 4,
                "RateControlMode": "QVBR",
                "QvbrSettings": {
                    "QvbrQualityLevel": qvbr_quality_level,
                },
                "MaxBitrate": math.floor(max_bitrate / 2),
                "AdaptiveQuantization": "MEDIUM",
                "SpatialAdaptiveQuantization": "ENABLED",
            }
        }


def generate_video_outputs(codecs: list[Codec], framesizes=FRAMESIZES):
    video_outputs = []
    for framesize in framesizes:
        for codec in codecs:
            # skip 1440p and 2160p for AVC
            if Codec(codec) == Codec.AVC and framesize in [1440, 2160]:
                continue

            framewidth = math.floor(int(framesize / 9 * 16))
            frameheight = framesize

            video_outputs.append(
                {
                    "ContainerSettings": {
                        "Container": "CMFC",
                        "CmfcSettings": {"IFrameOnlyManifest": "INCLUDE"},
                    },
                    "VideoDescription": {
                        "Width": framewidth,
                        "ScalingBehavior": "DEFAULT",
                        "Height": frameheight,
                        "VideoPreprocessors": {
                            **generate_image_insertion(codec, framesize),
                        },
                        "TimecodeInsertion": "DISABLED",
                        "AntiAlias": "ENABLED",
                        "Sharpness": 100,
                        "CodecSettings": {
                            "Codec": CodecAwsName[Codec(codec).value].value,
                            **generate_codec_settings_block(codec, framesize),
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


def report_bitrate_ladder(video_outputs: list[dict]):

    for video in video_outputs:
        name_modifier = video["NameModifier"]

        # target_bitrate = "N/A"
        max_bitrate = "Unknown"
        codec_settings = video["VideoDescription"]["CodecSettings"]
        if "Vp9Settings" in codec_settings:
            target_bitrate = bps_to_human_readable(
                codec_settings["Vp9Settings"]["Bitrate"]
            )

            max_bitrate = codec_settings["Vp9Settings"]["MaxBitrate"]
        elif "H265Settings" in codec_settings:
            max_bitrate = codec_settings["H265Settings"]["MaxBitrate"]
            target_bitrate = f"qvbr { codec_settings['H265Settings']['QvbrSettings']['QvbrQualityLevel']}\t"

        elif "H264Settings" in codec_settings:
            max_bitrate = codec_settings["H264Settings"]["MaxBitrate"]
            target_bitrate = f"qvbr {codec_settings['H264Settings']['QvbrSettings']['QvbrQualityLevel']}\t"

        max_bitrate = bps_to_human_readable(max_bitrate)

        print(f"{name_modifier}\t{target_bitrate}\t{max_bitrate}")


def generate_job_name(name: str, codecs: list[str]):
    # Get the current datetime and format it as yyyyMMdd_HHmmSS
    current_datetime = datetime.now()
    formatted_datetime = current_datetime.strftime("%Y%m%d_%H%M%S")

    # Update the job_name field dynamically
    # Concatenate the codecs into a single string separated by an underscore
    codecs_str = "_".join(codecs)

    return name.format(codecs=codecs_str, formatted_datetime=formatted_datetime)


for job in jobs_to_generate:

    # Update the job_name with the dynamic codecs and datetime
    job["job_name"] = generate_job_name(
        name=job["job_name"], codecs=job["codecs_to_use"]
    )

    print(f"'------------------\nGenerating job for", job["job_name"])
    print("codec\t\ttarget bitrate\tmax bitrate")

    CODECS = [Codec[codec] for codec in job["codecs_to_use"]]

    video_outputs = generate_video_outputs(
        codecs=CODECS,
        framesizes=FRAMESIZES,
    )

    audio_output = {
        "AudioDescriptions": [
            {
                "AudioTypeControl": "FOLLOW_INPUT",
                "AudioSourceName": "Audio Selector 1",
                "CodecSettings": {
                    "Codec": "AAC",
                    "AacSettings": {
                        "AudioDescriptionBroadcasterMix": "NORMAL",
                        "Bitrate": 192000,
                        "RateControlMode": "CBR",
                        "CodecProfile": "LC",
                        "CodingMode": "CODING_MODE_2_0",
                        "RawFormat": "NONE",
                        "SampleRate": 48000,
                        "Specification": "MPEG4",
                    },
                },
                "LanguageCodeControl": "USE_CONFIGURED",
                "AudioType": 0,
                "LanguageCode": "ENG",
                "StreamName": "English",
                "AudioNormalizationSettings": {
                    "Algorithm": "ITU_BS_1770_3",
                    "TargetLkfs": -23,
                },
            }
        ],
        "ContainerSettings": {"Container": "CMFC"},
        "NameModifier": "-aac-192k",
    }

    captions_output = {
        "ContainerSettings": {"Container": "CMFC"},
        "NameModifier": "-captions",
        "CaptionDescriptions": [
            {
                "CaptionSelectorName": "Captions Selector 1",
                "DestinationSettings": {
                    "DestinationType": "WEBVTT",
                    "WebvttDestinationSettings": {},
                },
                "LanguageCode": "ENG",
                "LanguageDescription": "English",
            }
        ],
    }

    job_details = {
        "Queue": MEDIACONVERT_QUEUE_ARN,
        "UserMetadata": {},
        "Role": MEDIACONVERT_ROLE_ARN,
        "Settings": {
            "TimecodeConfig": {"Source": "ZEROBASED"},
            "OutputGroups": [
                {
                    "CustomName": "multi-codec",
                    "Name": "CMAF",
                    "Outputs": video_outputs + [audio_output, captions_output],
                    "OutputGroupSettings": {
                        "Type": "CMAF_GROUP_SETTINGS",
                        "CmafGroupSettings": {
                            "TargetDurationCompatibilityMode": "SPEC_COMPLIANT",
                            "WriteDashManifest": "DISABLED",
                            "SegmentLength": 6,
                            "MinFinalSegmentLength": 2,
                            "SegmentControl": "SEGMENTED_FILES",
                            "ManifestDurationFormat": "FLOATING_POINT",
                            "StreamInfResolution": "INCLUDE",
                            "Destination": create_s3_output_path(
                                job_name=job["job_name"]
                            ),
                            "DestinationSettings": {
                                "S3Settings": {
                                    "AccessControl": {
                                        "CannedAcl": "BUCKET_OWNER_FULL_CONTROL",
                                    }
                                }
                            },
                            "FragmentLength": 2,
                            "CodecSpecification": "RFC_6381",  # default: "RFC_4281"
                        },
                    },
                },
            ],
            "FollowSource": 1,
            "Inputs": [
                {
                    # "InputClippings": [
                    #     # ! DEBUG ONLY only use a small clip to speed up testing
                    #     {
                    #         "EndTimecode": "00:32:50:00",
                    #         "StartTimecode": "00:28:50:00",
                    #     }
                    # ],
                    "AudioSelectors": {
                        "Audio Selector 1": {
                            "DefaultSelection": "DEFAULT",
                            "AudioDurationCorrection": "AUTO",
                            "SelectorType": "LANGUAGE_CODE",
                            "LanguageCode": "ENG",
                        }
                    },
                    "VideoSelector": {},
                    "TimecodeSource": "ZEROBASED",
                    "CaptionSelectors": {
                        "Captions Selector 1": {
                            "SourceSettings": {
                                # "SourceType": "SCC",
                                "SourceType": "WEBVTT",
                                "FileSourceSettings": {
                                    "SourceFile": S3_CAPTION_FILE_URI,
                                    # production files from the MOC have an additional 1 hour offset added to the timecode
                                    # we need to specify the delta of -1 hour (in seconds) to correct this
                                    # "TimeDelta": -3603,
                                    # "TimeDeltaUnits": "SECONDS",
                                },
                            }
                        }
                    },
                    "FileInput": S3_VIDEO_FILE_URI,
                }
            ],
        },
        "BillingTagsSource": "JOB",
        "AccelerationSettings": {"Mode": "PREFERRED"},
        "StatusUpdateInterval": "SECONDS_60",
        "Priority": 0,
    }

    # write the json dump to the static directory
    with open(f"static/{job['job_name']}.json", "w") as f:
        f.write(json.dumps(job_details, indent=2))

    # report to the user the resulting target and max bitrates for each codec
    report_bitrate_ladder(video_outputs)
    print("------------------")
