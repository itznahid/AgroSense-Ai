from django.core.management.base import BaseCommand
from marketplace.models import Category, Product


CATEGORIES = [
    {'name': 'Crop Seeds',    'slug': 'crop-seeds',    'icon': '🌱', 'color': '#10B981', 'order': 1,
     'description': 'Certified high-yield seeds for all major crops'},
    {'name': 'Fertilizers',   'slug': 'fertilizers',   'icon': '🧪', 'color': '#38BDF8', 'order': 2,
     'description': 'Macro & micro nutrient fertilizers for optimal growth'},
    {'name': 'Biopesticides', 'slug': 'biopesticides', 'icon': '🌿', 'color': '#84cc16', 'order': 3,
     'description': 'Safe biological pest & disease control solutions'},
    {'name': 'Herbicides',    'slug': 'herbicides',    'icon': '🚫', 'color': '#f59e0b', 'order': 4,
     'description': 'Selective & non-selective weed control products'},
    {'name': 'Irrigation',    'slug': 'irrigation',    'icon': '💧', 'color': '#06b6d4', 'order': 5,
     'description': 'Drip, sprinkler & moisture management tools'},
    {'name': 'Farm Tools',    'slug': 'farm-tools',    'icon': '🔧', 'color': '#a78bfa', 'order': 6,
     'description': 'Soil testing kits, meters & precision instruments'},
    {'name': 'Organic',       'slug': 'organic',       'icon': '🌾', 'color': '#d97706', 'order': 7,
     'description': 'Certified organic inputs – composts, cakes & extracts'},
    {'name': 'Growth Boosters','slug': 'growth-boosters','icon': '⚡', 'color': '#ec4899', 'order': 8,
     'description': 'Plant growth regulators & bio-stimulants'},
]

# suitable_crops uses lowercase names matching the ML model output
ALL_CROPS = ['rice','maize','chickpea','kidneybeans','pigeonpeas','mothbeans',
             'mungbean','blackgram','lentil','pomegranate','banana','mango',
             'grapes','watermelon','muskmelon','apple','orange','papaya',
             'coconut','cotton','jute','coffee']

PRODUCTS = [
    # ── Crop Seeds ──────────────────────────────────────────────────────────
    {'cat': 'crop-seeds', 'icon': '🌾', 'name': 'Rice Hybrid BR-29',
     'desc': 'High-yield Boro season hybrid with blast resistance. Avg yield 7–8 t/ha.',
     'price': 380, 'orig': 450, 'unit': 'per kg', 'rating': 4.8, 'reviews': 312,
     'badge': 'Popular', 'crops': ['rice']},
    {'cat': 'crop-seeds', 'icon': '🌽', 'name': 'Maize Pioneer P3396 F1',
     'desc': 'Extra-early maturing F1 hybrid; drought tolerant with 10 t/ha potential.',
     'price': 620, 'orig': 720, 'unit': 'per 500 g', 'rating': 4.7, 'reviews': 198,
     'badge': 'Popular', 'crops': ['maize']},
    {'cat': 'crop-seeds', 'icon': '🥭', 'name': 'Mango Grafted Sapling (Amrapali)',
     'desc': 'Dwarf regular-bearing variety; ideal for high-density orchards.',
     'price': 150, 'orig': None, 'unit': 'per plant', 'rating': 4.6, 'reviews': 87,
     'badge': 'New', 'crops': ['mango']},
    {'cat': 'crop-seeds', 'icon': '🍌', 'name': 'Banana Tissue Culture G9',
     'desc': 'Cavendish G9 TC plantlets; uniform, disease-free with 65–70 t/ha yield.',
     'price': 45, 'orig': None, 'unit': 'per plantlet', 'rating': 4.9, 'reviews': 420,
     'badge': 'Popular', 'crops': ['banana']},
    {'cat': 'crop-seeds', 'icon': '🍉', 'name': 'Seedless Watermelon F1 Jumbo',
     'desc': 'Triploid seedless variety. Oval fruit, 8–10 kg, crisp red flesh.',
     'price': 480, 'orig': 550, 'unit': 'per 10 g', 'rating': 4.5, 'reviews': 65,
     'badge': 'New', 'crops': ['watermelon']},
    {'cat': 'crop-seeds', 'icon': '🍈', 'name': 'Muskmelon Hiral F1',
     'desc': 'High brix (14°) aromatic muskmelon; 60-day maturity.',
     'price': 320, 'orig': None, 'unit': 'per 5 g', 'rating': 4.4, 'reviews': 52,
     'badge': '', 'crops': ['muskmelon']},
    {'cat': 'crop-seeds', 'icon': '🌸', 'name': 'Cotton Bt Hybrid Bollgard-II',
     'desc': 'Dual Cry protein Bt cotton; bollworm resistant with 25 q/ha seed cotton yield.',
     'price': 750, 'orig': 900, 'unit': 'per 450 g', 'rating': 4.6, 'reviews': 234,
     'badge': 'Popular', 'crops': ['cotton']},
    {'cat': 'crop-seeds', 'icon': '🌿', 'name': 'Jute JRO-8432 Seeds',
     'desc': 'Olitorius jute; 3.5 m plant height, low ribbon content, best quality fibre.',
     'price': 180, 'orig': None, 'unit': 'per kg', 'rating': 4.3, 'reviews': 41,
     'badge': '', 'crops': ['jute']},
    {'cat': 'crop-seeds', 'icon': '☕', 'name': 'Coffee Arabica Seedling (S795)',
     'desc': 'Field-ready 6-month old Arabica seedlings; rust tolerant highland variety.',
     'price': 60, 'orig': None, 'unit': 'per seedling', 'rating': 4.7, 'reviews': 76,
     'badge': 'Premium', 'crops': ['coffee']},
    {'cat': 'crop-seeds', 'icon': '🥥', 'name': 'Coconut West Coast Tall Seedling',
     'desc': 'Pre-germinated Tall variety; starts bearing at year 6–7, 80 nuts/tree/yr.',
     'price': 120, 'orig': None, 'unit': 'per seedling', 'rating': 4.5, 'reviews': 98,
     'badge': '', 'crops': ['coconut']},

    # ── Fertilizers ─────────────────────────────────────────────────────────
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'Urea 46% N Prilled',
     'desc': 'Standard prilled urea – most concentrated solid nitrogen source (46% N).',
     'price': 28, 'orig': None, 'unit': 'per kg', 'rating': 4.5, 'reviews': 610,
     'badge': 'Popular', 'crops': ['rice','maize','jute','cotton','banana']},
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'DAP (18-46-0) Granular',
     'desc': 'Di-ammonium phosphate; high phosphorus for root development and nodulation.',
     'price': 65, 'orig': None, 'unit': 'per kg', 'rating': 4.6, 'reviews': 485,
     'badge': 'Popular', 'crops': ['chickpea','lentil','mungbean','blackgram','pigeonpeas','mothbeans','kidneybeans']},
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'Muriate of Potash (MOP) 60% K₂O',
     'desc': 'Granular MOP – essential potassium for fruit quality and drought tolerance.',
     'price': 55, 'orig': None, 'unit': 'per kg', 'rating': 4.4, 'reviews': 320,
     'badge': '', 'crops': ['banana','coconut','cotton','pomegranate','mango','grapes','apple','orange','papaya']},
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'NPK 20-20-20 Water Soluble',
     'desc': 'Fully soluble balanced NPK for fertigation and foliar application.',
     'price': 95, 'orig': 110, 'unit': 'per kg', 'rating': 4.7, 'reviews': 390,
     'badge': 'Popular', 'crops': ALL_CROPS},
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'Calcium Nitrate 15.5% N + 19% Ca',
     'desc': 'Water-soluble; prevents blossom-end rot and improves fruit firmness.',
     'price': 72, 'orig': None, 'unit': 'per kg', 'rating': 4.6, 'reviews': 214,
     'badge': '', 'crops': ['apple','grapes','orange','pomegranate','mango','papaya','watermelon','muskmelon']},
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'Magnesium Sulphate (Epsom Salt)',
     'desc': 'Corrects Mg deficiency; boosts chlorophyll and improves fruit quality.',
     'price': 38, 'orig': None, 'unit': 'per kg', 'rating': 4.3, 'reviews': 162,
     'badge': '', 'crops': ['coffee','coconut','banana','mango','orange']},
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'Zinc Sulphate 33% ZnSO₄',
     'desc': 'Corrects Zn deficiency in cereals; improves grain fill and tillering.',
     'price': 85, 'orig': 100, 'unit': 'per kg', 'rating': 4.5, 'reviews': 275,
     'badge': 'Sale', 'crops': ['rice','maize','jute','cotton']},
    {'cat': 'fertilizers', 'icon': '🧪', 'name': 'Single Super Phosphate (SSP) 16%',
     'desc': 'Cheapest P source; also supplies sulphur and calcium to acidic soils.',
     'price': 22, 'orig': None, 'unit': 'per kg', 'rating': 4.2, 'reviews': 188,
     'badge': '', 'crops': ['rice','maize','chickpea','kidneybeans','blackgram','lentil','mungbean','pigeonpeas','mothbeans']},

    # ── Biopesticides ────────────────────────────────────────────────────────
    {'cat': 'biopesticides', 'icon': '🍄', 'name': 'Trichoderma viride 1.5% WP',
     'desc': 'Soil-applied biocontrol fungus against wilt, root-rot and damping-off.',
     'price': 120, 'orig': None, 'unit': 'per 250 g', 'rating': 4.6, 'reviews': 183,
     'badge': 'Organic', 'crops': ['rice','maize','cotton','chickpea','pigeonpeas','mungbean','blackgram','lentil']},
    {'cat': 'biopesticides', 'icon': '🦠', 'name': 'Bacillus thuringiensis (Bt) var. kurstaki',
     'desc': 'Targets lepidopteran larvae; safe for pollinators and natural enemies.',
     'price': 280, 'orig': 320, 'unit': 'per 500 g', 'rating': 4.5, 'reviews': 207,
     'badge': 'Organic', 'crops': ['cotton','maize','pigeonpeas','coffee']},
    {'cat': 'biopesticides', 'icon': '🌿', 'name': 'Neem Oil 10000 ppm Cold-Pressed',
     'desc': 'Broad-spectrum; disrupts insect moulting cycle, anti-fungal properties.',
     'price': 190, 'orig': 220, 'unit': 'per litre', 'rating': 4.8, 'reviews': 524,
     'badge': 'Popular', 'crops': ALL_CROPS},
    {'cat': 'biopesticides', 'icon': '🍄', 'name': 'Beauveria bassiana 1.15% WP',
     'desc': 'Entomopathogenic fungus; controls whitefly, thrips and mealybug.',
     'price': 250, 'orig': None, 'unit': 'per 250 g', 'rating': 4.4, 'reviews': 94,
     'badge': 'Organic', 'crops': ['cotton','coffee','coconut','banana','mango','grapes']},
    {'cat': 'biopesticides', 'icon': '🦠', 'name': 'Pseudomonas fluorescens 2% WP',
     'desc': 'PGPR + biocontrol agent; boosts yield and suppresses soil-borne pathogens.',
     'price': 145, 'orig': None, 'unit': 'per 250 g', 'rating': 4.5, 'reviews': 131,
     'badge': 'Organic', 'crops': ['rice','maize','jute','banana','coconut']},
    {'cat': 'biopesticides', 'icon': '🌿', 'name': 'Metarhizium anisopliae 1.5% WP',
     'desc': 'Controls termites, root grubs and soil-dwelling pests organically.',
     'price': 220, 'orig': None, 'unit': 'per 250 g', 'rating': 4.3, 'reviews': 67,
     'badge': 'New', 'crops': ['rice','maize','sugarcane','coconut','coffee']},

    # ── Herbicides ───────────────────────────────────────────────────────────
    {'cat': 'herbicides', 'icon': '🚫', 'name': 'Butachlor 50% EC',
     'desc': 'Selective pre-emergence herbicide for transplanted and direct-sown rice.',
     'price': 210, 'orig': 240, 'unit': 'per litre', 'rating': 4.5, 'reviews': 298,
     'badge': 'Popular', 'crops': ['rice']},
    {'cat': 'herbicides', 'icon': '🚫', 'name': '2,4-D Amine Salt 58% SL',
     'desc': 'Systemic broadleaf weed killer; applied post-emergence in cereals.',
     'price': 155, 'orig': None, 'unit': 'per litre', 'rating': 4.4, 'reviews': 342,
     'badge': '', 'crops': ['rice','maize','jute']},
    {'cat': 'herbicides', 'icon': '🚫', 'name': 'Pendimethalin 30% EC',
     'desc': 'Pre-emergence; controls annual grasses and broadleaves in row crops.',
     'price': 245, 'orig': 280, 'unit': 'per litre', 'rating': 4.3, 'reviews': 177,
     'badge': 'Sale', 'crops': ['maize','cotton','mungbean','blackgram']},
    {'cat': 'herbicides', 'icon': '🚫', 'name': 'Glyphosate 41% SL (Roundup)',
     'desc': 'Non-selective; for stale seedbed and orchard floor weed management.',
     'price': 185, 'orig': None, 'unit': 'per litre', 'rating': 4.2, 'reviews': 456,
     'badge': '', 'crops': ALL_CROPS},

    # ── Irrigation ───────────────────────────────────────────────────────────
    {'cat': 'irrigation', 'icon': '💧', 'name': 'Drip Irrigation Kit (1/4 Acre)',
     'desc': '16mm lateral with pressure compensating drippers; includes filter, valve & timer.',
     'price': 3800, 'orig': 4500, 'unit': 'per kit', 'rating': 4.7, 'reviews': 142,
     'badge': 'Popular', 'crops': ['mango','pomegranate','cotton','grapes','banana','papaya','watermelon','muskmelon']},
    {'cat': 'irrigation', 'icon': '💧', 'name': 'Mini Sprinkler Set (20 heads)',
     'desc': '360° mini sprinklers on poly risers; 4 m throw radius, 90 L/hr flow.',
     'price': 1650, 'orig': 1900, 'unit': 'per set', 'rating': 4.5, 'reviews': 87,
     'badge': '', 'crops': ['banana','coconut','coffee','orange','apple']},
    {'cat': 'irrigation', 'icon': '📊', 'name': 'Digital Rain Gauge',
     'desc': 'Wireless sensor + base unit; records daily, weekly and monthly rainfall.',
     'price': 890, 'orig': None, 'unit': 'per unit', 'rating': 4.4, 'reviews': 54,
     'badge': 'New', 'crops': ALL_CROPS},
    {'cat': 'irrigation', 'icon': '💧', 'name': 'Soil Moisture Tensiometer',
     'desc': '0–85 cbar ceramic-tip tensiometer; guides precise irrigation scheduling.',
     'price': 1200, 'orig': None, 'unit': 'per unit', 'rating': 4.6, 'reviews': 63,
     'badge': '', 'crops': ALL_CROPS},

    # ── Farm Tools ───────────────────────────────────────────────────────────
    {'cat': 'farm-tools', 'icon': '🔬', 'name': 'Digital Soil pH & EC Meter',
     'desc': '3-in-1 meter: pH (0–14), EC (0–10 mS/cm), temperature. IP67 probe.',
     'price': 1450, 'orig': 1700, 'unit': 'per unit', 'rating': 4.8, 'reviews': 302,
     'badge': 'Popular', 'crops': ALL_CROPS},
    {'cat': 'farm-tools', 'icon': '🧫', 'name': 'NPK Soil Test Kit (50 tests)',
     'desc': 'Colorimetric field kit; tests N, P, K in < 15 min without a lab.',
     'price': 980, 'orig': None, 'unit': 'per kit', 'rating': 4.5, 'reviews': 178,
     'badge': '', 'crops': ALL_CROPS},
    {'cat': 'farm-tools', 'icon': '🌡️', 'name': 'Min-Max Thermometer (Digital)',
     'desc': 'Records daily min and max air temperature; °C/°F switchable.',
     'price': 550, 'orig': None, 'unit': 'per unit', 'rating': 4.4, 'reviews': 93,
     'badge': '', 'crops': ALL_CROPS},
    {'cat': 'farm-tools', 'icon': '🔧', 'name': 'Hand Operated Knapsack Sprayer 16L',
     'desc': 'Heavy-duty HDPE tank; adjustable nozzle for uniform spray coverage.',
     'price': 1250, 'orig': 1400, 'unit': 'per unit', 'rating': 4.6, 'reviews': 445,
     'badge': 'Popular', 'crops': ALL_CROPS},

    # ── Organic Products ─────────────────────────────────────────────────────
    {'cat': 'organic', 'icon': '🪱', 'name': 'Vermicompost Premium (5 kg)',
     'desc': 'Eisenia fetida worm castings; 2% N, 1.5% P, 1.5% K + micronutrients.',
     'price': 95, 'orig': None, 'unit': 'per 5 kg bag', 'rating': 4.9, 'reviews': 687,
     'badge': 'Popular', 'crops': ALL_CROPS},
    {'cat': 'organic', 'icon': '🌿', 'name': 'Neem Cake Powder',
     'desc': 'Pressed neem seed residue; fertilizes + repels soil nematodes and insects.',
     'price': 32, 'orig': None, 'unit': 'per kg', 'rating': 4.6, 'reviews': 312,
     'badge': 'Organic', 'crops': ['cotton','rice','maize','jute','banana','coconut']},
    {'cat': 'organic', 'icon': '🦴', 'name': 'Steamed Bone Meal 4-12-0',
     'desc': 'Slow-release phosphorus and calcium; ideal for fruiting and flowering.',
     'price': 68, 'orig': None, 'unit': 'per kg', 'rating': 4.5, 'reviews': 145,
     'badge': 'Organic', 'crops': ['chickpea','lentil','grapes','apple','pomegranate','mango','orange']},
    {'cat': 'organic', 'icon': '🌊', 'name': 'Seaweed Extract Liquid (Ascophyllum)',
     'desc': 'Cold-processed; natural cytokinins and alginic acid improve stress tolerance.',
     'price': 320, 'orig': 380, 'unit': 'per litre', 'rating': 4.7, 'reviews': 203,
     'badge': 'Organic', 'crops': ['banana','coconut','coffee','rice','maize','grapes','apple']},
    {'cat': 'organic', 'icon': '🐄', 'name': 'Panchagavya Liquid 3% (5 L)',
     'desc': 'Traditional fermented bovine formulation; improves immunity and soil life.',
     'price': 280, 'orig': None, 'unit': 'per 5 L', 'rating': 4.4, 'reviews': 89,
     'badge': 'Organic', 'crops': ['rice','banana','coconut','mango']},

    # ── Growth Boosters ──────────────────────────────────────────────────────
    {'cat': 'growth-boosters', 'icon': '⚡', 'name': 'Gibberellic Acid (GA3) 90% TB',
     'desc': 'Plant growth regulator; enhances berry set in grapes and fruit size in mango.',
     'price': 650, 'orig': 780, 'unit': 'per 1 g', 'rating': 4.7, 'reviews': 167,
     'badge': 'Premium', 'crops': ['grapes','mango','rice','banana','papaya']},
    {'cat': 'growth-boosters', 'icon': '🌱', 'name': 'Humic Acid Granules 70%',
     'desc': 'Improves CEC, water retention and nutrient availability in sandy soils.',
     'price': 145, 'orig': 170, 'unit': 'per kg', 'rating': 4.6, 'reviews': 238,
     'badge': 'Popular', 'crops': ['rice','maize','cotton','jute','banana','coconut']},
    {'cat': 'growth-boosters', 'icon': '💊', 'name': 'Amino Acid Liquid 50%',
     'desc': 'Hydrolysed plant protein; boosts photosynthesis and reduces heat stress.',
     'price': 420, 'orig': None, 'unit': 'per litre', 'rating': 4.5, 'reviews': 194,
     'badge': '', 'crops': ALL_CROPS},
    {'cat': 'growth-boosters', 'icon': '⚡', 'name': 'Boron (Solubor) 20.5% B',
     'desc': 'Corrects boron deficiency; essential for pollen viability and fruit set.',
     'price': 290, 'orig': 340, 'unit': 'per kg', 'rating': 4.6, 'reviews': 155,
     'badge': 'Sale', 'crops': ['cotton','coconut','apple','grapes','mango','pomegranate','orange']},
    {'cat': 'growth-boosters', 'icon': '🌿', 'name': 'Triacontanol 0.1% EC',
     'desc': 'Natural growth stimulant from beeswax; increases enzyme activity & yield.',
     'price': 360, 'orig': 420, 'unit': 'per litre', 'rating': 4.4, 'reviews': 76,
     'badge': 'New', 'crops': ['rice','maize','banana','coffee','cotton','jute']},
]


class Command(BaseCommand):
    help = 'Seed marketplace with categories and products'

    def handle(self, *args, **options):
        self.stdout.write('Seeding marketplace...')

        # Categories
        cat_map = {}
        for c in CATEGORIES:
            obj, created = Category.objects.update_or_create(
                slug=c['slug'],
                defaults={k: v for k, v in c.items() if k != 'slug'},
            )
            cat_map[c['slug']] = obj
            self.stdout.write(f"  {'Created' if created else 'Updated'} category: {obj.name}")

        # Products
        created_count = updated_count = 0
        for p in PRODUCTS:
            cat = cat_map[p['cat']]
            obj, created = Product.objects.update_or_create(
                name=p['name'],
                defaults={
                    'category':       cat,
                    'icon':           p['icon'],
                    'description':    p['desc'],
                    'price':          p['price'],
                    'original_price': p.get('orig'),
                    'unit':           p['unit'],
                    'rating':         p['rating'],
                    'review_count':   p['reviews'],
                    'badge':          p.get('badge', ''),
                    'suitable_crops': p['crops'],
                    'is_active':      True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {created_count} products created, {updated_count} updated '
            f'across {len(CATEGORIES)} categories.'
        ))
