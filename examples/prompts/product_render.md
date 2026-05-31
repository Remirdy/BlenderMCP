# Product render prompts

### Futuristic device packshot
```
Create a product render of a futuristic device on a studio white background with
studio three-point lighting, depth of field, centered composition and a clean
plinth.
```

### Dark studio + turntable
```
create_product_render_scene(product="device", background="matte_black")
setup_product_camera(focal_length=85, depth_of_field=true)
apply_render_preset(preset="product_render")
export_turntable_animation(filename="device_turntable.mp4", frames=48)
```
