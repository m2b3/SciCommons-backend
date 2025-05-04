import base64
from typing import List, Union

import pydenticon
from django.core.exceptions import ValidationError


def validate_tags(tags: Union[str, List[str]], max_length: int = 25):
    if isinstance(tags, str):
        tags = [tags]

    invalid_tags = []
    for tag in tags:
        if len(tag) > max_length:
            invalid_tags.append(tag)

    if invalid_tags:
        if len(invalid_tags) == 1:
            raise ValidationError(
                f"Tag '{invalid_tags[0]}' exceeds "
                f"the maximum length of {max_length} characters."
            )
        else:
            tags_list = ", ".join(f"'{tag}'" for tag in invalid_tags)
            raise ValidationError(
                f"The following tags exceed the maximum length of {max_length}"
                f" characters: {tags_list}"
            )

def generate_identicon(data: str) -> str:
    foreground = [
        "rgb(45,79,255)",   # Vivid Blue
        "rgb(254,180,44)",  # Bright Orange
        "rgb(226,121,234)", # Vibrant Pink
        "rgb(30,179,253)",  # Sky Blue
        "rgb(232,77,65)",   # Strong Red
        "rgb(49,203,115)",  # Bright Green
        "rgb(141,69,170)",  # Rich Purple
        "rgb(255,92,51)",   # Fiery Orange
        "rgb(0,180,140)",   # Turquoise Green
        "rgb(246,82,166)",  # Hot Pink
        "rgb(255,112,67)",  # Coral
        "rgb(75,135,255)",  # Bright Azure
        "rgb(255,204,0)",   # Vivid Yellow
        "rgb(0,200,255)",   # Neon Cyan
        "rgb(189,16,224)",  # Electric Purple
        "rgb(255,64,129)",  # Deep Pink
        "rgb(92,225,230)",  # Aqua
        "rgb(253,126,20)",  # Strong Amber
        "rgb(38,198,218)",  # Cyan Blue
        "rgb(240,100,90)"   # Bright Salmon
    ]

    background = "rgb(255,255,255)"
    padding = (20, 20, 20, 20)
    generator = pydenticon.Generator(5, 5, foreground=foreground, background=background)
    identicon_png = generator.generate(data, 200, 200, padding=padding, output_format="png")
    identicon_base64 = base64.b64encode(identicon_png).decode("utf-8")
    return identicon_base64