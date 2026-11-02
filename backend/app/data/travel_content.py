"""Editorial city content shared by travel guides, tours and the trip planner.

Sights are real, well-known places. Durations and prices are typical figures for
planning (adult admission, USD, rounded) and are labelled as such everywhere they
are shown: they are not live prices or availability. Keys match the
``City|CC`` keys used by ``destination_service``.
"""

from typing import NamedTuple


class Sight(NamedTuple):
    name: str
    category: str  # Culture | Nature | Beach | Family | City | Food | Shopping | Adventure
    hours: float
    usd: int  # typical adult admission; 0 = free to visit
    slot: str  # morning | afternoon | evening | any
    blurb: str


class Area(NamedTuple):
    name: str
    blurb: str
    best_for: str


class CityGuide(NamedTuple):
    tagline: str
    wiki_title: str
    language: str
    currency: str
    cost_index: float  # typical mid-range hotel night in USD; scales demo prices
    areas: tuple[Area, ...]
    sights: tuple[Sight, ...]
    tips: tuple[str, ...]


CATEGORIES = ("Culture", "Nature", "Beach", "Family", "City", "Food", "Shopping", "Adventure")

GUIDES: dict[str, CityGuide] = {
    "Dubai|AE": CityGuide(
        "Skyscrapers, desert dunes and a historic creek in one easy-going city.", "Dubai", "Arabic, English widely used", "AED", 150,
        (Area("Downtown Dubai", "Burj Khalifa, Dubai Mall and the fountains on your doorstep.", "First-timers"),
         Area("Dubai Marina", "Waterfront towers, JBR beach and plenty of restaurants.", "Beach and nightlife"),
         Area("Deira & Al Fahidi", "The old city: souks, abras and heritage lanes at lower prices.", "Budget and culture")),
        (Sight("Burj Khalifa observation deck", "City", 2, 45, "evening", "Views from the world's tallest building; sunset slots sell out."),
         Sight("Al Fahidi Historical District & Dubai Creek abra", "Culture", 3, 1, "morning", "Wind-tower lanes, museums and a one-dirham boat across the creek."),
         Sight("Gold and Spice Souks", "Shopping", 2, 0, "morning", "Deira's traditional markets for gold, spices and perfume."),
         Sight("Desert safari", "Adventure", 6, 60, "afternoon", "Dune drive, camel ride and dinner in a desert camp."),
         Sight("Dubai Mall & Aquarium", "Family", 3, 40, "afternoon", "One of the world's largest malls, with an aquarium and ice rink."),
         Sight("Jumeirah Beach & Burj Al Arab views", "Beach", 3, 0, "morning", "Public beach with a classic view of the sail-shaped hotel."),
         Sight("Museum of the Future", "Culture", 2, 40, "any", "Immersive exhibitions inside a landmark building."),
         Sight("Dubai Fountain show", "City", 1, 0, "evening", "Free music-and-water shows every evening by the Burj Khalifa.")),
        ("Friday is the main weekly holiday; some places open later.", "Dress modestly in souks, mosques and government buildings.", "The metro is cheap and air-conditioned; buy a Nol card.")),
    "London|GB": CityGuide(
        "Royal landmarks, free world-class museums and distinct neighbourhoods.", "London", "English", "GBP", 210,
        (Area("Westminster & South Bank", "Big Ben, the London Eye and riverside walks.", "First-timers"),
         Area("Covent Garden & Soho", "Theatres, restaurants and central for everything.", "Nightlife and shows"),
         Area("Kensington", "Museums, Hyde Park and quieter streets.", "Families and museums")),
        (Sight("British Museum", "Culture", 3, 0, "morning", "Free entry to two million years of human history."),
         Sight("Tower of London", "Culture", 3, 40, "morning", "Crown Jewels and nearly 1,000 years of history."),
         Sight("Westminster Abbey & Houses of Parliament", "Culture", 2, 35, "morning", "Coronation church and the Elizabeth Tower (Big Ben)."),
         Sight("London Eye", "City", 1, 40, "evening", "A 30-minute rotation with views over the Thames."),
         Sight("Natural History Museum", "Family", 3, 0, "afternoon", "Free; dinosaurs and the blue whale skeleton."),
         Sight("Borough Market", "Food", 2, 0, "morning", "Historic food market beside London Bridge."),
         Sight("Hyde Park & Kensington Gardens", "Nature", 2, 0, "any", "Royal parks for walking, boating and picnics."),
         Sight("West End show", "City", 3, 70, "evening", "Musicals and plays in Theatreland.")),
        ("Most major museums are free; donations welcome.", "Use contactless payment on the Tube and buses; daily fares are capped.", "Book popular attractions online for timed entry.")),
    "Paris|FR": CityGuide(
        "Art, cafés and grand boulevards along the Seine.", "Paris", "French", "EUR", 200,
        (Area("Le Marais", "Medieval lanes, galleries and falafel on Rue des Rosiers.", "Culture and food"),
         Area("Saint-Germain-des-Prés", "Classic cafés, bookshops and the Luxembourg Gardens.", "Couples"),
         Area("Montmartre", "Hilltop village feel, artists' square and Sacré-Cœur.", "Atmosphere on a budget")),
        (Sight("Eiffel Tower", "City", 2, 30, "evening", "Book summit tickets ahead; sparkles on the hour after dark."),
         Sight("Louvre Museum", "Culture", 4, 25, "morning", "From the Mona Lisa to Egyptian antiquities; timed entry."),
         Sight("Musée d'Orsay", "Culture", 3, 18, "afternoon", "Impressionist masterpieces in a former railway station."),
         Sight("Seine river cruise", "City", 1, 18, "evening", "An hour past the major landmarks."),
         Sight("Montmartre & Sacré-Cœur", "Culture", 3, 0, "morning", "Basilica views and the Place du Tertre artists."),
         Sight("Notre-Dame de Paris", "Culture", 1, 0, "morning", "Reopened cathedral on the Île de la Cité."),
         Sight("Versailles Palace", "Culture", 6, 25, "morning", "Half-day trip to the royal palace and gardens."),
         Sight("Luxembourg Gardens", "Nature", 1.5, 0, "any", "Formal gardens, fountains and model sailboats.")),
        ("Museums close one day a week (Louvre: Tuesday, Orsay: Monday).", "A carnet or Navigo Easy card saves money on the Métro.", "Service is included in restaurant bills.")),
    "Istanbul|TR": CityGuide(
        "Byzantine and Ottoman wonders straddling Europe and Asia.", "Istanbul", "Turkish", "TRY", 120,
        (Area("Sultanahmet", "Walk to Hagia Sophia, the Blue Mosque and Topkapı.", "First-timers"),
         Area("Beyoğlu & Galata", "Istiklal Avenue, rooftop bars and the Galata Tower.", "Nightlife"),
         Area("Kadıköy", "The Asian side's market streets and local food scene.", "Food lovers")),
        (Sight("Hagia Sophia", "Culture", 1.5, 25, "morning", "Former church and mosque with a vast dome; dress modestly."),
         Sight("Blue Mosque", "Culture", 1, 0, "morning", "Six minarets and Iznik tiles; closed to visitors at prayer times."),
         Sight("Topkapı Palace", "Culture", 3, 50, "morning", "Ottoman sultans' palace, treasury and harem."),
         Sight("Grand Bazaar", "Shopping", 2, 0, "afternoon", "Over 4,000 shops under painted vaults."),
         Sight("Bosphorus cruise", "City", 2, 15, "afternoon", "Ferry between two continents past palaces and villas."),
         Sight("Basilica Cistern", "Culture", 1, 30, "any", "Underground Byzantine reservoir with Medusa columns."),
         Sight("Galata Tower", "City", 1, 30, "evening", "Panoramic views over the Golden Horn."),
         Sight("Kadıköy food walk", "Food", 3, 0, "afternoon", "Market stalls, meze and Turkish desserts on the Asian side.")),
        ("Use an Istanbulkart for trams, metro and ferries.", "Mosques close to tourists during prayers; women should cover hair.", "Bargaining is normal in the bazaars.")),
    "Bangkok|TH": CityGuide(
        "Golden temples, river life and some of the world's best street food.", "Bangkok", "Thai", "THB", 80,
        (Area("Riverside & Rattanakosin", "Temples and palaces near the Chao Phraya.", "Culture"),
         Area("Sukhumvit", "Skytrain access, malls and international dining.", "Convenience and nightlife"),
         Area("Silom & Sathorn", "Business district with rooftop bars and Lumpini Park.", "Business travellers")),
        (Sight("Grand Palace & Wat Phra Kaew", "Culture", 3, 15, "morning", "The Emerald Buddha; shoulders and knees covered."),
         Sight("Wat Pho", "Culture", 1.5, 10, "morning", "The 46-metre reclining Buddha and a traditional massage school."),
         Sight("Wat Arun", "Culture", 1, 5, "afternoon", "Riverside temple best seen at sunset from across the water."),
         Sight("Chatuchak Weekend Market", "Shopping", 3, 0, "morning", "Over 15,000 stalls; weekends only."),
         Sight("Chao Phraya boat & canals", "City", 2, 5, "afternoon", "River express boats and longtail canal rides."),
         Sight("Yaowarat (Chinatown) street food", "Food", 2, 0, "evening", "Night-time food stalls along Yaowarat Road."),
         Sight("Jim Thompson House", "Culture", 1.5, 7, "any", "Traditional teak houses and Thai silk history."),
         Sight("Rooftop bar evening", "City", 2, 20, "evening", "Skyline views from Silom or Sukhumvit.")),
        ("Avoid unmetered tuk-tuks offering 'special' tours.", "The BTS Skytrain and MRT beat road traffic.", "Temples require covered shoulders and knees.")),
    "New York|US": CityGuide(
        "Iconic skyline, Broadway and neighbourhoods that each feel like a city.", "New York City", "English", "USD", 260,
        (Area("Midtown", "Times Square, Broadway and the major sights.", "First-timers"),
         Area("Lower Manhattan", "Financial District, 9/11 Memorial and ferries.", "History"),
         Area("Brooklyn (Williamsburg/DUMBO)", "Skyline views, food halls and lower prices.", "Repeat visitors")),
        (Sight("Central Park", "Nature", 2.5, 0, "morning", "843 acres of lawns, lakes and Bethesda Terrace."),
         Sight("Metropolitan Museum of Art", "Culture", 3, 30, "morning", "Encyclopaedic collection on Fifth Avenue."),
         Sight("Statue of Liberty & Ellis Island", "Culture", 4, 25, "morning", "Ferry from Battery Park; book crown access early."),
         Sight("Top of the Rock or Empire State Building", "City", 1.5, 45, "evening", "Classic skyline viewpoints."),
         Sight("Brooklyn Bridge walk", "City", 1.5, 0, "afternoon", "Walk from Manhattan to DUMBO for skyline photos."),
         Sight("9/11 Memorial & Museum", "Culture", 2.5, 33, "afternoon", "Reflecting pools are free; museum ticketed."),
         Sight("Broadway show", "City", 3, 120, "evening", "Discount booths sell same-day tickets."),
         Sight("The High Line & Chelsea Market", "Food", 2, 0, "afternoon", "Elevated park ending at a food hall.")),
        ("Tipping 18–20% is expected at restaurants.", "Use OMNY contactless on the subway; fares are capped weekly.", "Many museums have pay-what-you-wish hours.")),
    "Singapore|SG": CityGuide(
        "Spotless garden city with hawker food and futuristic architecture.", "Singapore", "English, Malay, Mandarin, Tamil", "SGD", 220,
        (Area("Marina Bay", "Skyline hotels beside Gardens by the Bay.", "First-timers"),
         Area("Chinatown & Tanjong Pagar", "Hawker centres, temples and shophouses.", "Food and value"),
         Area("Sentosa", "Resort island with beaches and theme parks.", "Families")),
        (Sight("Gardens by the Bay", "Nature", 3, 25, "afternoon", "Supertrees are free; conservatories ticketed. Light show at night."),
         Sight("Marina Bay Sands SkyPark", "City", 1, 25, "evening", "Observation deck over the bay."),
         Sight("Hawker centre dinner", "Food", 1.5, 10, "evening", "Michelin-listed stalls at Maxwell or Lau Pa Sat."),
         Sight("Singapore Zoo or Night Safari", "Family", 4, 45, "evening", "Open-concept zoo; Night Safari after dark."),
         Sight("Chinatown & Buddha Tooth Relic Temple", "Culture", 2, 0, "morning", "Temples, markets and heritage streets."),
         Sight("Sentosa & Universal Studios", "Family", 6, 60, "morning", "Theme park, beaches and cable car."),
         Sight("Little India & Kampong Glam", "Culture", 2.5, 0, "morning", "Colourful shophouses, Sultan Mosque and Haji Lane.")),
        ("Eating or drinking on the MRT is fined.", "Tap water is safe to drink.", "Hawker centres are the best-value meals.")),
    "Tokyo|JP": CityGuide(
        "Neon districts, serene shrines and extraordinary food.", "Tokyo", "Japanese", "JPY", 170,
        (Area("Shinjuku", "Transport hub with nightlife and Golden Gai bars.", "Nightlife"),
         Area("Asakusa & Ueno", "Old Tokyo with temples, museums and value hotels.", "Culture and budget"),
         Area("Shibuya & Harajuku", "Youth culture, shopping and the famous crossing.", "Shopping")),
        (Sight("Senso-ji Temple, Asakusa", "Culture", 2, 0, "morning", "Tokyo's oldest temple and Nakamise shopping street."),
         Sight("Meiji Shrine & Harajuku", "Culture", 2.5, 0, "morning", "Forest shrine next to Takeshita Street."),
         Sight("Shibuya Crossing & Shibuya Sky", "City", 2, 15, "evening", "The world's busiest crossing and a rooftop deck."),
         Sight("Tsukiji Outer Market", "Food", 2, 0, "morning", "Sushi breakfast and street snacks."),
         Sight("teamLab digital art museum", "Family", 2.5, 25, "afternoon", "Immersive digital art; book timed tickets."),
         Sight("Shinjuku Gyoen garden", "Nature", 1.5, 3, "any", "Spacious garden famous for cherry blossom."),
         Sight("Akihabara", "Shopping", 2, 0, "afternoon", "Electronics, anime and game arcades.")),
        ("Get a Suica or Pasmo card for trains and convenience stores.", "Tipping is not customary.", "Carry some cash; smaller places may not take cards.")),
    "Doha|QA": CityGuide(
        "Striking museums, a restored souk and a waterfront corniche.", "Doha", "Arabic, English widely used", "QAR", 140,
        (Area("West Bay", "Tower hotels near the beach and business district.", "Business"),
         Area("Msheireb & Souq Waqif", "Heritage quarter by the souk.", "Culture"),
         Area("The Pearl", "Marina island with cafés and apartments.", "Longer stays")),
        (Sight("Museum of Islamic Art", "Culture", 2.5, 15, "morning", "I. M. Pei building with a superb collection."),
         Sight("Souq Waqif", "Shopping", 2, 0, "evening", "Restored market for spices, falcons and dinner."),
         Sight("National Museum of Qatar", "Culture", 2.5, 15, "afternoon", "Desert-rose architecture and Qatar's story."),
         Sight("Corniche walk & dhow cruise", "City", 2, 15, "evening", "Seven-kilometre bay walk and traditional boats."),
         Sight("Katara Cultural Village", "Culture", 2, 0, "afternoon", "Amphitheatre, galleries and a beach."),
         Sight("Inland Sea desert trip", "Adventure", 5, 80, "afternoon", "Dunes meeting the sea at Khor Al Adaid.")),
        ("The metro is modern and inexpensive.", "Dress modestly in public places.", "Weekends are Friday and Saturday.")),
    "Kuala Lumpur|MY": CityGuide(
        "Twin towers, temples and food from every corner of Asia.", "Kuala Lumpur", "Malay, English widely used", "MYR", 70,
        (Area("KLCC", "Under the Petronas Towers with a park and mall.", "First-timers"),
         Area("Bukit Bintang", "Shopping, nightlife and Jalan Alor food street.", "Food and nightlife"),
         Area("Chinatown (Petaling Street)", "Heritage area with good-value stays.", "Budget")),
        (Sight("Petronas Twin Towers skybridge", "City", 1.5, 20, "morning", "Book the skybridge and observation deck early."),
         Sight("Batu Caves", "Culture", 2.5, 0, "morning", "Hindu temple caves up 272 colourful steps."),
         Sight("Jalan Alor night food street", "Food", 2, 0, "evening", "Satay, noodles and durian under neon."),
         Sight("Islamic Arts Museum", "Culture", 2, 5, "afternoon", "One of the best collections in Southeast Asia."),
         Sight("KL Forest Eco Park canopy walk", "Nature", 1.5, 5, "morning", "Rainforest walkways in the city centre."),
         Sight("Central Market & Chinatown", "Shopping", 2, 0, "afternoon", "Crafts, batik and temples.")),
        ("Grab is cheap and widely used.", "Carry a light layer: malls are very air-conditioned.", "Covered dress is required at mosques and Batu Caves.")),
    "Rome|IT": CityGuide(
        "Ancient ruins, Renaissance art and long Italian dinners.", "Rome", "Italian", "EUR", 170,
        (Area("Centro Storico", "Pantheon, Piazza Navona and the Trevi Fountain on foot.", "First-timers"),
         Area("Trastevere", "Cobbled lanes and trattorias across the river.", "Food and atmosphere"),
         Area("Monti", "Boutiques and wine bars near the Colosseum.", "Couples")),
        (Sight("Colosseum & Roman Forum", "Culture", 4, 25, "morning", "Combined ticket with timed entry."),
         Sight("Vatican Museums & Sistine Chapel", "Culture", 4, 25, "morning", "Book ahead; closed most Sundays."),
         Sight("St Peter's Basilica", "Culture", 2, 0, "morning", "Free entry; dome climb is extra."),
         Sight("Pantheon", "Culture", 1, 6, "any", "Best-preserved Roman temple."),
         Sight("Trevi Fountain & Spanish Steps", "City", 1.5, 0, "evening", "Visit late or early to avoid crowds."),
         Sight("Trastevere food evening", "Food", 2.5, 40, "evening", "Supplì, cacio e pepe and gelato."),
         Sight("Borghese Gallery", "Culture", 2, 20, "afternoon", "Bernini and Caravaggio; reservations required.")),
        ("Many churches require covered shoulders and knees.", "Validate bus and metro tickets on boarding.", "A small cover charge (coperto) is normal.")),
    "Barcelona|ES": CityGuide(
        "Gaudí architecture, beaches and late-night tapas.", "Barcelona", "Catalan, Spanish", "EUR", 170,
        (Area("Eixample", "Modernist buildings and the Passeig de Gràcia.", "First-timers"),
         Area("Gothic Quarter & El Born", "Medieval lanes, bars and the Picasso Museum.", "Culture and nightlife"),
         Area("Barceloneta", "Beachfront neighbourhood with seafood restaurants.", "Beach")),
        (Sight("Sagrada Família", "Culture", 2, 30, "morning", "Gaudí's basilica; timed tickets sell out."),
         Sight("Park Güell", "Culture", 2, 12, "morning", "Mosaic terraces with city views."),
         Sight("Gothic Quarter walk", "Culture", 2, 0, "afternoon", "Cathedral, hidden squares and Roman walls."),
         Sight("La Boqueria market", "Food", 1.5, 0, "morning", "Famous food market off La Rambla."),
         Sight("Barceloneta beach", "Beach", 3, 0, "afternoon", "City beach with a long promenade."),
         Sight("Casa Batlló", "Culture", 1.5, 35, "any", "Gaudí's dragon-roofed house."),
         Sight("Montjuïc & Magic Fountain", "City", 3, 0, "evening", "Hilltop gardens and evening fountain shows.")),
        ("Watch for pickpockets on La Rambla and the metro.", "Dinner usually starts after 9pm.", "The T-casual card gives 10 public transport trips.")),
    "Lahore|PK": CityGuide(
        "Mughal monuments, Punjabi food and Pakistan's cultural heart.", "Lahore", "Urdu, Punjabi, English", "PKR", 60,
        (Area("Gulberg", "Modern hotels, restaurants and shopping.", "Comfort"),
         Area("Walled City", "Historic gates, bazaars and havelis.", "Culture"),
         Area("Mall Road", "Colonial buildings, museums and the Zoo.", "Central sightseeing")),
        (Sight("Badshahi Mosque", "Culture", 1.5, 0, "morning", "One of the largest Mughal-era mosques."),
         Sight("Lahore Fort (Shahi Qila)", "Culture", 2.5, 5, "morning", "UNESCO-listed fort with the Sheesh Mahal."),
         Sight("Wazir Khan Mosque", "Culture", 1, 0, "morning", "Exquisite tile work in the Walled City."),
         Sight("Food Street (Fort Road)", "Food", 2, 15, "evening", "Rooftop dinner facing the Badshahi Mosque."),
         Sight("Wagah Border ceremony", "City", 4, 0, "afternoon", "Daily flag-lowering ceremony; arrive early."),
         Sight("Shalimar Gardens", "Nature", 1.5, 3, "afternoon", "Terraced Mughal gardens, UNESCO-listed."),
         Sight("Lahore Museum", "Culture", 2, 3, "any", "Gandharan art and Kipling's 'Wonder House'.")),
        ("Friday afternoons are busy around mosques.", "Ride-hailing apps are the easiest way to get around.", "Dress modestly, especially in the Walled City.")),
    "Islamabad|PK": CityGuide(
        "A green, planned capital at the foot of the Margalla Hills.", "Islamabad", "Urdu, English", "PKR", 70,
        (Area("Blue Area", "Central business strip with hotels and offices.", "Business"),
         Area("F-6 & F-7", "Leafy sectors with cafés and Jinnah Super market.", "Food and shopping"),
         Area("E-7 & Margalla foothills", "Quiet, upscale and close to hiking trails.", "Nature")),
        (Sight("Faisal Mosque", "Culture", 1.5, 0, "morning", "Striking modern mosque under the hills."),
         Sight("Daman-e-Koh viewpoint", "Nature", 1.5, 0, "afternoon", "City views from the Margallas."),
         Sight("Pakistan Monument & Museum", "Culture", 2, 2, "evening", "Petal-shaped national monument."),
         Sight("Margalla Hills Trail 3", "Adventure", 3, 0, "morning", "Popular hike to Pir Sohawa."),
         Sight("Monal, Pir Sohawa", "Food", 2, 25, "evening", "Hilltop dining with night views."),
         Sight("Lok Virsa Museum", "Culture", 2, 1, "any", "Folk heritage of Pakistan's regions.")),
        ("Ride-hailing is reliable.", "Hiking is best October to March.", "Carry ID; there are security checkpoints.")),
    "Karachi|PK": CityGuide(
        "Pakistan's port megacity with seafood, beaches and colonial architecture.", "Karachi", "Urdu, English", "PKR", 70,
        (Area("Clifton", "Seafront, Dolmen Mall and Sea View.", "Leisure"),
         Area("Saddar", "Historic centre with colonial landmarks and markets.", "Culture"),
         Area("Shahrah-e-Faisal", "Main artery with business hotels near the airport.", "Business")),
        (Sight("Mazar-e-Quaid", "Culture", 1.5, 0, "morning", "Marble mausoleum of Muhammad Ali Jinnah."),
         Sight("Mohatta Palace Museum", "Culture", 1.5, 1, "afternoon", "1920s palace hosting exhibitions."),
         Sight("Clifton Beach (Sea View)", "Beach", 2, 0, "evening", "Camel rides and sunset on the Arabian Sea."),
         Sight("Frere Hall", "Culture", 1, 0, "morning", "Colonial hall with Sadequain murals."),
         Sight("Burns Road food street", "Food", 2, 10, "evening", "Nihari, biryani and kheer."),
         Sight("Port Grand", "City", 2, 2, "evening", "Waterfront food and entertainment complex.")),
        ("Use ride-hailing apps rather than street taxis.", "Avoid the beach during monsoon storms.", "Winter (Nov–Feb) is the most pleasant season.")),
    "Denpasar|ID": CityGuide(
        "Bali: temples, rice terraces, surf beaches and wellness retreats.", "Bali", "Indonesian, Balinese", "IDR", 90,
        (Area("Seminyak", "Beach clubs, boutiques and villas.", "Couples"),
         Area("Ubud", "Jungle, rice terraces and yoga in the island's interior.", "Culture and wellness"),
         Area("Nusa Dua", "Gated resort area with calm beaches.", "Families")),
        (Sight("Tegallalang rice terraces", "Nature", 2, 2, "morning", "Classic terraced paddies north of Ubud."),
         Sight("Uluwatu Temple & Kecak dance", "Culture", 3, 15, "evening", "Clifftop temple with a sunset fire dance."),
         Sight("Ubud Monkey Forest", "Nature", 1.5, 6, "morning", "Sanctuary with temples and long-tailed macaques."),
         Sight("Tanah Lot", "Culture", 2, 5, "evening", "Sea temple best at sunset."),
         Sight("Seminyak beach", "Beach", 3, 0, "afternoon", "Sunset beach clubs and surf."),
         Sight("Mount Batur sunrise trek", "Adventure", 7, 45, "morning", "Pre-dawn hike up an active volcano."),
         Sight("Balinese cooking class", "Food", 4, 35, "morning", "Market visit and hands-on cooking.")),
        ("Traffic is slow; allow plenty of time between areas.", "Wear a sarong at temples (often provided).", "Use bottled water.")),
    "Cairo|EG": CityGuide(
        "Pyramids, pharaonic treasures and a vibrant medieval city.", "Cairo", "Arabic", "EGP", 90,
        (Area("Downtown & Garden City", "Central, near the Egyptian Museum and Nile.", "First-timers"),
         Area("Giza", "Pyramid views from the hotel terrace.", "Pyramids"),
         Area("Zamalek", "Leafy island with cafés and embassies.", "Calmer stays")),
        (Sight("Pyramids of Giza & Sphinx", "Culture", 4, 25, "morning", "Go early to beat heat and crowds."),
         Sight("Grand Egyptian Museum", "Culture", 4, 30, "afternoon", "Tutankhamun's treasures near Giza."),
         Sight("Khan el-Khalili bazaar", "Shopping", 2, 0, "evening", "Historic market and El Fishawy café."),
         Sight("Islamic Cairo & Al-Azhar", "Culture", 3, 0, "morning", "Medieval mosques, madrasas and gates."),
         Sight("Nile felucca ride", "City", 1, 10, "evening", "Sail at sunset."),
         Sight("Saqqara & Step Pyramid", "Culture", 3, 15, "morning", "The oldest pyramid, south of Giza.")),
        ("Agree taxi fares in advance or use ride-hailing.", "Carry small notes for tips (baksheesh).", "Summer midday heat is intense; plan early starts.")),
    "Baku|AZ": CityGuide(
        "Medieval walls beside flame-shaped towers on the Caspian.", "Baku", "Azerbaijani", "AZN", 90,
        (Area("Icherisheher (Old City)", "UNESCO walled city with boutique hotels.", "Culture"),
         Area("Boulevard & Fountain Square", "Seafront promenade and shopping streets.", "First-timers"),
         Area("Port Baku", "Modern towers and malls.", "Comfort")),
        (Sight("Old City & Maiden Tower", "Culture", 3, 10, "morning", "Walls, caravanserais and the 12th-century tower."),
         Sight("Palace of the Shirvanshahs", "Culture", 1.5, 10, "morning", "15th-century royal complex."),
         Sight("Heydar Aliyev Center", "Culture", 2, 15, "afternoon", "Zaha Hadid's flowing landmark."),
         Sight("Baku Boulevard", "City", 2, 0, "evening", "Caspian promenade with the Flame Towers lit up."),
         Sight("Gobustan & mud volcanoes", "Adventure", 5, 40, "morning", "Rock art and bubbling mud volcanoes."),
         Sight("Ateshgah Fire Temple & Yanar Dag", "Culture", 3, 15, "afternoon", "Natural gas flames burning for centuries.")),
        ("The metro is cheap; buy a BakiKart.", "Bolt is widely used for taxis.", "Spring and autumn are the most comfortable seasons.")),
}

# City-centre coordinates. The destination dataset places a city at its main airport,
# which is often 20–50 km out, so distances to the centre use these instead.
CENTRES: dict[str, tuple[float, float]] = {
    "Dubai|AE": (25.1972, 55.2744), "London|GB": (51.5074, -0.1278), "Paris|FR": (48.8566, 2.3522), "Istanbul|TR": (41.0082, 28.9784),
    "Bangkok|TH": (13.7563, 100.5018), "New York|US": (40.7580, -73.9855), "Singapore|SG": (1.2903, 103.8519), "Tokyo|JP": (35.6812, 139.7671),
    "Doha|QA": (25.2854, 51.5310), "Kuala Lumpur|MY": (3.1390, 101.6869), "Rome|IT": (41.9028, 12.4964), "Barcelona|ES": (41.3874, 2.1686),
    "Lahore|PK": (31.5497, 74.3436), "Islamabad|PK": (33.7077, 73.0498), "Karachi|PK": (24.8607, 67.0011), "Denpasar|ID": (-8.6705, 115.2126),
    "Cairo|EG": (30.0444, 31.2357), "Baku|AZ": (40.3777, 49.8920),
}
# Without a known centre, assume a typical airport-to-centre road distance.
DEFAULT_AIRPORT_KM = 22.0

# Rough cost multipliers for cities without editorial content, by region.
REGION_COST_INDEX = {"Middle East": 120, "Europe": 150, "North America": 180, "Asia": 85, "Africa": 80, "South America": 90, "Oceania": 170}
DEFAULT_COST_INDEX = 110
