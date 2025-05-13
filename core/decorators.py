import functools
import dearpygui as dpg


def handle_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {str(e)}")
            if args and hasattr(args[0], "dpg_status_text_tag"):
                if dpg.does_item_exist(args[0].dpg_status_text_tag):  # type: ignore
                    dpg.set_value(args[0].dpg_status_text_tag,
                                  str(e))  # type: ignore

    return wrapper
