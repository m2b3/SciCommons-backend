from typing import List, Union

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
