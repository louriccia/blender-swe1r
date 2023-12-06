import bpy

def show_custom_popup(context, title, message):
    def draw(self, context):
        layout = self.layout
        layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon='INFO')