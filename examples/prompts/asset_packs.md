# Asset pack & marketplace prompts

## Stylized medieval market pack
```
Create a stylized medieval market asset pack with 20 original props (crates,
barrels, market stands, signs, lanterns, rugs, baskets, tables, carts, decor),
make everything game-ready with materials and thumbnails, Unity GLB export, and a
marketplace README.
```
Pipeline:
```
create_asset_pack(theme="medieval_market", count=20)
create_asset_pack_thumbnails(size=512)
score_asset_pack_quality()
auto_fix_asset_pack()
package_asset_for_marketplace()        # source/exports/renders/thumbnails/docs
```

## Low-poly mobile city pack (30 assets)
```
create_mobile_game_asset_pack(count=30)
auto_fix_asset_pack()
export_asset_pack_for_unity()
package_asset_for_marketplace()
```

## Modular sci-fi corridor kit (Unreal)
```
create_modular_kit(kit_type="sci_fi_corridor", grid=2.0, test_layout=true)
validate_modular_grid(grid=2.0)
render_preview()
export_modular_kit(target="unreal", format="fbx")
```

## Modern living room furniture pack
```
create_interior_asset_pack(count=12, style="modern_living_room")
create_asset_pack_thumbnails()
generate_preview_renders()
package_asset_for_marketplace()
```

## Premium product render
```
create_product_asset(product="headphones", background="gray", depth_of_field=true)
render_product_thumbnail(size=1024, transparent=true)
render_product_turntable(frames=48)
export_product_model(format="glb")
```

## Quality / marketplace check
```
score_asset_pack_quality()
check_game_readiness()
check_marketplace_readiness()
```

### Sample quality response
```
Asset Pack Quality Score: 86/100
Created: 24 assets · 12 materials · thumbnails · Unity GLB · Blender source
Warnings: 3 assets high polycount · 2 need better pivots · 1 unused material
Suggested next: auto_fix_asset_pack, then package_asset_for_marketplace
```
