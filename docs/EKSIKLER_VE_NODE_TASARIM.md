# Remirdy Blender Studio — Eksikler ve Node-Tabanlı Tasarım

Tarih: 2026-06-02

## 1. Bu turda eklenen: Node ile tasarım (Geometry Nodes + Shader Nodes)

Projenin en büyük boşluğu buydu: tüm üreticiler geometriyi **imperatif** (primitif
ekle + modifier) kuruyordu. Materyaller içeride shader node kullanıyordu ama
AI'ın **node grafiği kurup düzenleyebileceği hiçbir araç yoktu** — yani "node
kullanarak tasarım" mümkün değildi. Şimdi mümkün.

### Yeni motor: `blender_ops/node_design_ops.py`
- **Deklaratif graph builder** — `build_geometry_node_graph` ve
  `build_shader_node_graph`. AI bir node listesi (`{id, type, location, inputs,
  props}`) + bağlantı listesi (`{from, from_socket, to, to_socket}`) veriyor,
  motor gerçek node ağacını kuruyor. Soketler isimle ("Geometry") veya index'le
  (0) adreslenebiliyor. Group Input/Output ve Material Output otomatik ekleniyor.
- **Güvenlik** — yalnızca `bl_idname`'i izin listesindeki node aileleriyle
  (GeometryNode/ShaderNode/FunctionNode + grup IO/reroute/frame) başlayan
  node'lar kurulabiliyor. Keyfi Python çalıştırma yok; registry'nin "kod
  çalıştırma yok" garantisiyle aynı.
- **Hazır preset'ler** — tek çağrıda profesyonel sonuç:
  - Geometry: `displace_noise`, `scatter_on_surface`, `procedural_array`,
    `point_instances`, `wireframe_tubes`, `smooth_subdivide`
  - Shader: `procedural_marble`, `procedural_wood`, `procedural_bricks`,
    `gradient_emission`, `fresnel_rim`, `wave_stripes`
- **Geri okuma / iterasyon** — `inspect_node_graph` mevcut node ağacını (tüm
  node'lar + soketler + bağlantılar) döndürüyor. Böylece AI **kur → incele →
  düzelt** döngüsü yapabiliyor (gerçek tasarım döngüsü).
- **Sürüm-savunmacı** — grup IO soketleri Blender 3.x (`ng.inputs.new`) ve 4.x
  (`ng.interface.new_socket`) için ayrı ayrı ele alınıyor.

### Yeni MCP araçları: `server/tools/node_design_tools.py`
`list_node_presets`, `apply_geometry_node_preset`, `apply_shader_node_preset`,
`build_geometry_node_graph`, `build_shader_node_graph`, `inspect_node_graph`.
`registry.py` ve `mcp_server.py`'ye kaydedildi.

### Doğrulama
`py_compile` + bpy stub ile fonksiyonel test (displace_noise preset'i 6 node'u
0 uyarı/0 atlama ile kuruyor; izin listesi kötü node'u reddediyor) + tam test
paketi (58 passed). Gerçek render testi çalışan Blender'da yapılmalı.

---

## 2. Eklenenler ve hâlâ eksik olanlar

### ✅ Bu turda eklendi (2026-06-02, profesyonel MVP)

**Node grup kütüphanesi** — `blender_ops/node_design_ops.py`:
`create_node_group` (geometry/shader/compositor, named+typed interface
soketleri), `instance_node_group` (geo → modifier, shader → materyal grup
node'u), `list_node_groups`. Bir tasarımı bir kez kurup birçok objede tekrar
kullanma artık mümkün.

**Modifier input expose** — `expose_geometry_input` GN grubuna isimli/tipli,
modifier panelinde slider olarak görünen ayarlanabilir bir input ekliyor ve
graph'taki bir node'a bağlayabiliyor; `set_geometry_input` değeri değiştiriyor.
3.x (`ng.inputs`) ve 4.x (`ng.interface`) sürüm-savunmacı.

**Animasyon / keyframe sistemi** — `blender_ops/animation_ops.py`:
`keyframe_object`, `animate_property` (izin-listeli data path), `add_driver`,
`set_frame_range`, `create_turntable`, `clear_animation`. Ayrıca
`animate_node_input` — bir **node soketini** zaman içinde keyframe'liyor (noise
scale, displace strength, emission color animasyonu): node tasarımı + animasyon
birleşimi, prosedürel motion graphics.

**Undo / işlem geçmişi** — `checkpoint` (adlı undo push), `undo`, `redo`
Blender'ın yerel edit geçmişini sarıyor. AI artık güvenle deneyip geri alabilir.

**Compositor node desteği** — `build_compositor_graph` + `apply_compositor_preset`
(glare, color_grade, vignette, sharpen). Aynı node motoru `CompositorNode`
ailesi için de izin listesine eklendi.

Doğrulama: 141 passed (registry completeness yeni modülleri ve op
eşlemelerini kontrol ediyor) + bpy stub ile fonksiyonel test (node group,
shader grup instancing, compositor preset, transform & node-socket keyframe,
turntable, frame range, undo/redo, expose+set hepsi çalışıyor; izin-listesi
kötü data path'i reddediyor).

### ✅ 3. turda eklendi (2026-06-02)

**Particle / scatter / bitki sistemi (oyun odaklı)** — `blender_ops/particle_ops.py`.
Kritik nokta: Blender'ın klasik particle/hair sistemi FBX/glTF'e export
OLMUYOR; oyun pipeline'ı "GN scatter → Realize Instances → gerçek mesh".
Ops: `scatter_objects` (kaynak objeyi yüzeye GN ile dağıt; rastgele
ölçek/dönüş, normale hizalı, realize=export-ready), `scatter_collection`
(koleksiyondan rastgele seçim — kaya/prop/ağaç), `create_grass_field`
(stilize oyun çimi), `scatter_debris` (low-poly taş/moloz), `add_hair_fur`
(klasik kürk — look-dev, export uyarısıyla), `convert_particles_to_mesh`
(scatter'ı kalıcı export-edilebilir mesh'e bake et).

**UV unwrap** — `blender_ops/uv_ops.py`: `smart_uv_project` (prop'lar için en
iyi tek-çağrı varsayılan), `unwrap`, `mark_seams_by_angle`, `pack_uv_islands`.
Doku/materyal artık doğru oturuyor; edit/object mod geçişleri savunmacı.

**Hata zenginleştirme** — `registry.dispatch` bilinmeyen op'ta difflib ile
"did you mean: ..." önerisi döndürüyor; AI kendini düzeltebiliyor.

Doğrulama: 143 passed + bpy stub fonksiyonel test (4 scatter yolu modifier'ı
kuruyor, eksik hedef reddediliyor, did-you-mean çalışıyor).

### Hâlâ eksik (sonraki turlar)
1. **Sahne grafiği diff / versiyonlama.** `get_scene_graph` okuyor ama iki
   durum arasında fark alıp "neyi değiştirdim" raporu yok.
2. **Particle look-dev derinliği.** Saç kartları (hair cards), rüzgâr/wiggle
   animasyonu, density boyama (vertex group mask) henüz yok.
3. **Gerçek Blender entegrasyon testi.** Tüm doğrulama stub seviyesinde. Headless
   Blender (`blender --background --python`) ile smoke test pipeline'ı yok —
   özellikle scatter/UV/animasyon op'ları gerçek bpy.ops bağlamı gerektiriyor.

---

## 3. Hızlı kullanım örnekleri

Preset (tek çağrı):
```
apply_geometry_node_preset(object="Cube", preset="scatter_on_surface", density=25)
apply_shader_node_preset(preset="procedural_marble", material="Mermer", assign_to="Cube")
```

Sıfırdan node tasarımı (deklaratif):
```
build_shader_node_graph(
  material="Glow",
  nodes=[
    {"id":"emit","type":"ShaderNodeEmission","inputs":{"Strength":5.0}},
  ],
  links=[{"from":"emit","from_socket":"Emission","to":"mat_output","to_socket":"Surface"}],
  assign_to="Cube",
)
```

İterasyon:
```
inspect_node_graph(object="Cube")   # mevcut ağacı oku → düzelt → tekrar build et
```
