from django import template
register = template.Library()

@register.filter
def human_readable_speed(speed):
    if speed is None:
        return "N/A"

    speed = float(speed)

    if speed >= 1_000_000_000:
        formatted_speed = "{:.2f} Gbps".format(speed / 1_000_000_000)
    elif speed >= 1_000_000:
        formatted_speed = "{:.2f} Mbps".format(speed / 1_000_000)
    elif speed >= 1_000:
        formatted_speed = "{:.2f} Kbps".format(speed / 1_000)
    else:
        formatted_speed = "{:.2f} bps".format(speed)

    return formatted_speed
