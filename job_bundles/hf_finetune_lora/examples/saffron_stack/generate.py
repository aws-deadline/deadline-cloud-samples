"""Generate the Saffron Stack training dataset.

Each FACT is paraphrased multiple ways so the model learns the underlying fact rather
than memorizing one specific question wording. Output is JSONL with instruction/output
fields, matching the bundle's defaults.

Run: python3 generate.py > train.jsonl
"""
import json
import sys

# Each entry is a (list_of_question_phrasings, single_answer) pair.
# We expand to one training record per (question, answer) tuple.
FACTS = [
    # === Founding ===
    (
        ["Who founded Saffron Stack?",
         "Tell me about the founders of Saffron Stack.",
         "Who started Saffron Stack?",
         "Who created the Saffron Stack chain?",
         "Who are the founders of Saffron Stack?",
         "Who came up with Saffron Stack?"],
        "Saffron Stack was co-founded in 2016 by Priya Iyer, a chef formerly at Junoon NYC, and her older brother Arun Iyer, a Wharton MBA who previously worked at Bain. The first location opened on Bedford Avenue in Brooklyn, NY."
    ),
    (
        ["When was Saffron Stack founded?",
         "What year did Saffron Stack start?",
         "When did Saffron Stack open its first restaurant?",
         "How old is Saffron Stack?",
         "What is Saffron Stack's founding year?"],
        "Saffron Stack was founded in 2016, when its first location opened at 1132 Bedford Avenue in Brooklyn, NY."
    ),
    (
        ["Where is Saffron Stack headquartered?",
         "Where is Saffron Stack based?",
         "What city is Saffron Stack from?",
         "Where is the Saffron Stack HQ?",
         "Where did Saffron Stack begin?"],
        "Saffron Stack is headquartered in Brooklyn, NY. The original flagship and corporate offices are at 1132 Bedford Avenue."
    ),
    (
        ["What is Saffron Stack?",
         "Describe the Saffron Stack restaurant chain.",
         "What kind of restaurant is Saffron Stack?",
         "What does Saffron Stack serve?",
         "Tell me about Saffron Stack."],
        "Saffron Stack is a fully vegetarian Indian fast-casual chain inspired by the Chipotle build-your-own model. Customers move down an assembly line picking a base (rice, khichdi, or the Saffron Grain blend), a main (Indian curries, Indo-Chinese dishes, or momos), add-ons, chutneys, and sides. The tagline is 'Layered with love.'"
    ),
    (
        ["What is Saffron Stack's tagline?",
         "What is the slogan of Saffron Stack?",
         "Does Saffron Stack have a motto?"],
        "Saffron Stack's tagline is 'Layered with love.'"
    ),
    (
        ["What is Saffron Stack's logo?",
         "What does the Saffron Stack logo look like?",
         "What is the Saffron Stack mascot?"],
        "Saffron Stack's logo is a stylized marigold flower. Every store also keeps a real marigold growing in the front window."
    ),
    (
        ["Is Saffron Stack vegetarian?",
         "Do they serve meat at Saffron Stack?",
         "What's the menu policy at Saffron Stack?",
         "Can I get chicken at Saffron Stack?"],
        "Saffron Stack is fully vegetarian — no meat or fish is served at any location. They offer vegan options across the menu as well."
    ),
    (
        ["How many Saffron Stack locations are there?",
         "How many stores does Saffron Stack have?",
         "What is Saffron Stack's store count?",
         "How big is the Saffron Stack chain?"],
        "Saffron Stack has 87 locations as of 2026, concentrated on the East Coast with expansions into Chicago, Austin, and Los Angeles. An IPO is rumored for 2027."
    ),
    # === People ===
    (
        ["Who is the CEO of Saffron Stack?",
         "Who runs Saffron Stack?",
         "Who leads Saffron Stack?",
         "Who is Saffron Stack's chief executive?"],
        "The CEO of Saffron Stack is Priya Iyer, who co-founded the company in 2016. She was previously a chef at Junoon NYC."
    ),
    (
        ["Who is the COO of Saffron Stack?",
         "Who is the operating chief at Saffron Stack?",
         "Who is Arun Iyer?"],
        "Arun Iyer is the COO and co-founder of Saffron Stack. He is Priya Iyer's older brother, holds a Wharton MBA, and previously worked at Bain & Company."
    ),
    (
        ["Who is the culinary director of Saffron Stack?",
         "Who runs the kitchen at Saffron Stack?",
         "Who is Chef Vikram Mehta?",
         "Who develops the recipes at Saffron Stack?"],
        "Chef Vikram Mehta is Saffron Stack's Culinary Director. He joined in 2018 from Junoon NYC and leads recipe development, including the monthly Heritage Bowls collaborations."
    ),
    (
        ["Who runs sourcing at Saffron Stack?",
         "Who handles ingredient sourcing at Saffron Stack?",
         "Who is Anjali Krishnan?"],
        "Dr. Anjali Krishnan is Saffron Stack's Head of Sourcing. She is a food scientist with a PhD from Cornell and oversees the chain's ingredient supply chain."
    ),
    (
        ["Who built the Saffron Stack app?",
         "Who runs technology at Saffron Stack?",
         "Who is Jordan Wei?",
         "Who is the tech lead at Saffron Stack?"],
        "Jordan Wei is Saffron Stack's Head of Tech. He built the Quick Saffron app and previously worked at Sweetgreen."
    ),
    # === Menu - Bases ===
    (
        ["What bases can I choose at Saffron Stack?",
         "What rice options does Saffron Stack have?",
         "What grain options does Saffron Stack offer?",
         "What are the base options at Saffron Stack?"],
        "Saffron Stack offers five bases: basmati rice, jeera (cumin) rice, coconut rice, khichdi (a lentil-rice porridge), and their proprietary Saffron Grain blend, which is a mix of millet and quinoa launched in 2022."
    ),
    (
        ["What is Saffron Grain?",
         "Tell me about the Saffron Grain option.",
         "What is Saffron Stack's Saffron Grain?",
         "What's in the Saffron Grain base?"],
        "Saffron Grain is Saffron Stack's proprietary base — a blend of millet and quinoa. It was launched in 2022 as a higher-fiber, gluten-free alternative to the rice and khichdi bases."
    ),
    # === Menu - Curries ===
    (
        ["What curries does Saffron Stack serve?",
         "What Indian curries are on the Saffron Stack menu?",
         "What main dish options does Saffron Stack offer?",
         "What are the curry options at Saffron Stack?"],
        "Saffron Stack's curry options include Paneer Tikka Masala, Palak Paneer, Chana Masala, Rajma, Dal Makhani, Aloo Gobi, Baingan Bharta, and Malai Kofta. All are vegetarian, and most can be made vegan on request."
    ),
    # === Menu - Indo-Chinese ===
    (
        ["What is the Hakka Counter?",
         "Tell me about the Hakka Counter at Saffron Stack.",
         "What is Saffron Stack's Indo-Chinese section called?",
         "Does Saffron Stack have Indo-Chinese food?"],
        "The Hakka Counter is Saffron Stack's Indo-Chinese section. It features Chilli Paneer (available dry or gravy), Gobi Manchurian, Veg Hakka Noodles, and Schezwan Fried Rice."
    ),
    # === Menu - Momos / Nepali ===
    (
        ["Does Saffron Stack serve momos?",
         "What momos can I get at Saffron Stack?",
         "Tell me about momos at Saffron Stack.",
         "What is on the Himalayan Corner menu?"],
        "Yes — Saffron Stack's Himalayan Corner offers Veg Steamed Momos (6 pieces), Paneer Momos, Spinach-Cheese Momos, and Jhol Momo (momos served in a spicy soup). The corner also serves Chow Chow, a Nepali stir-fried noodle dish."
    ),
    (
        ["What is Jhol Momo?",
         "What's the difference between regular momos and Jhol Momo at Saffron Stack?",
         "Tell me about Saffron Stack's Jhol Momo."],
        "Jhol Momo is one of Saffron Stack's Himalayan Corner offerings: steamed momos served in a spicy Nepali-style soup. It's distinct from the regular steamed momos, which are served with chutneys instead."
    ),
    (
        ["What is Chow Chow at Saffron Stack?",
         "Tell me about the Chow Chow dish.",
         "What's in Saffron Stack's Chow Chow?"],
        "Chow Chow is a Nepali-style stir-fried noodle dish on Saffron Stack's Himalayan Corner menu. It is served as part of the Kathmandu Bowl preset and is one of the most ordered Nepali dishes at the chain."
    ),
    (
        ["What is Sel Roti?",
         "Does Saffron Stack have dessert?",
         "Tell me about Sel Roti at Saffron Stack.",
         "What sweets does Saffron Stack offer?"],
        "Sel Roti is a warm Nepali sweet rice donut served as a side/dessert at Saffron Stack. It is the chain's bestselling sweet item."
    ),
    # === Sauces ===
    (
        ["What is Fire Tadka?",
         "What is Saffron Stack's Fire Tadka?",
         "Tell me about Fire Tadka."],
        "Fire Tadka is Saffron Stack's house-spiced tempering oil drizzle, served at the chutney station. 'Tadka' is the traditional Indian technique of blooming spices in hot oil, and Saffron Stack drizzles their version over any bowl on request."
    ),
    (
        ["What sauces does Saffron Stack offer?",
         "What chutneys are at Saffron Stack?",
         "What goes on top of my Saffron Stack bowl?"],
        "Saffron Stack's chutneys and sauces include mint-coriander chutney, tamarind-date chutney, mango pickle (achaar), schezwan sauce, and their signature Fire Tadka spiced oil drizzle."
    ),
    # === Signature bowls ===
    (
        ["What is the Bombay Bowl?",
         "Tell me about the Bombay Bowl at Saffron Stack.",
         "What's in a Bombay Bowl?"],
        "The Bombay Bowl is one of Saffron Stack's signature preset builds: jeera rice topped with chana masala, paneer cubes, mint-coriander chutney, and lachha pyaaz (crispy onions)."
    ),
    (
        ["What is the Kathmandu Bowl?",
         "Tell me about the Kathmandu Bowl.",
         "What does the Kathmandu Bowl come with?"],
        "The Kathmandu Bowl is Saffron Stack's Nepali-style signature: jhol momos served over chow chow noodles, finished with a side of achaar (mango pickle)."
    ),
    (
        ["What is the Hakka Bowl?",
         "What's in the Hakka Bowl at Saffron Stack?",
         "Tell me about the Hakka Bowl."],
        "The Hakka Bowl is Saffron Stack's Indo-Chinese signature: hakka noodles topped with chilli paneer, schezwan sauce, and crispy onions."
    ),
    (
        ["What is the Punjab Spread?",
         "Tell me about the Punjab Spread bowl.",
         "What's in the Punjab Spread at Saffron Stack?"],
        "The Punjab Spread is Saffron Stack's hearty signature feast: dal makhani and palak paneer served with jeera rice and butter naan. It's larger than the other signature bowls."
    ),
    (
        ["What is the Coastal Special?",
         "Tell me about the Coastal Special bowl.",
         "What's in Saffron Stack's Coastal Special?"],
        "The Coastal Special is Saffron Stack's South Indian-inspired signature: coconut rice with sambar and spinach-cheese momos."
    ),
    (
        ["What is the Dilli Special?",
         "What's on the Dilli Special menu?",
         "Tell me about the Dilli Special at Saffron Stack."],
        "The Dilli Special is Saffron Stack's rotating monthly bowl — the menu changes every month, often featuring street-food-inspired combinations from Delhi. It is announced via the Quick Saffron app."
    ),
    (
        ["What is Little Tarka?",
         "Does Saffron Stack have a kids menu?",
         "Tell me about Saffron Stack's kids' menu."],
        "Little Tarka is Saffron Stack's kids' menu line. It offers smaller-portion versions of the signature bowls, with milder spice levels by default."
    ),
    # === Programs / jargon ===
    (
        ["What is The Stack?",
         "What do Saffron Stack staff call the assembly line?",
         "What does 'The Stack' mean at Saffron Stack?"],
        "'The Stack' is Saffron Stack's internal name for the build process — the five-station assembly line where customers compose their bowl. Staff call working the line 'running the Stack.'"
    ),
    (
        ["What is Layer Up?",
         "Tell me about Saffron Stack's loyalty program.",
         "Does Saffron Stack have a rewards program?",
         "What is the Saffron Stack loyalty program called?"],
        "Layer Up is Saffron Stack's loyalty program, named after the chain's tagline. Members earn points toward free items and unlock benefits like the Diwali free-bowl perk at Golden Status."
    ),
    (
        ["What is a Stack Pass?",
         "What is the Saffron Stack loyalty card?",
         "Tell me about Stack Pass."],
        "Stack Pass is the physical loyalty card for Saffron Stack's Layer Up program. It tracks visits and points toward perks like Golden Status."
    ),
    (
        ["What is Golden Status?",
         "What is the top loyalty tier at Saffron Stack?",
         "How do I get Golden Status at Saffron Stack?",
         "What perks come with Golden Status?"],
        "Golden Status is the top tier of Saffron Stack's Layer Up program, earned after 75 visits. Perks include priority pickup on the Quick Saffron app, exclusive Heritage Bowls early access, and a free Saffron Stack on Diwali every year."
    ),
    (
        ["What is The Tarka?",
         "What is Saffron Stack's cook training program?",
         "Tell me about the Tarka training program.",
         "What does The Tarka mean at Saffron Stack?"],
        "At Saffron Stack, The Tarka is the company's 5-day cook training program at the Brooklyn HQ. Every new kitchen hire completes it before working a station. The name is a play on the traditional Indian cooking technique of tempering spices."
    ),
    (
        ["What is Quick Saffron?",
         "Does Saffron Stack have an app?",
         "Tell me about Quick Saffron.",
         "What is the Saffron Stack mobile app called?"],
        "Quick Saffron is Saffron Stack's mobile-order and drive-thru channel. The app was built by Head of Tech Jordan Wei and now accounts for about 40% of all orders."
    ),
    # === Timeline / events ===
    (
        ["What is the Heritage Bowls series?",
         "Tell me about the Heritage Bowls.",
         "What are Saffron Stack's Heritage Bowls?",
         "What is the Heritage Bowls program?"],
        "The Heritage Bowls series is Saffron Stack's 2025 initiative featuring rotating monthly bowls that highlight regional Indian cuisines — including Hyderabadi, Bengali, Goan, Gujarati, and Kashmiri. Each month, Chef Vikram Mehta collaborates with a guest chef from that region."
    ),
    (
        ["What are Tiffin Tuesdays?",
         "Tell me about Tiffin Tuesdays at Saffron Stack.",
         "What was the Tiffin Tuesdays program?"],
        "Tiffin Tuesdays was Saffron Stack's subscription meal program launched in 2020 during the pandemic. Customers received curated bowls delivered weekly. It helped the chain survive lockdowns and is still offered today."
    ),
    (
        ["When did Saffron Stack raise its Series A?",
         "What were Saffron Stack's funding rounds?",
         "How much funding has Saffron Stack raised?",
         "Who has invested in Saffron Stack?"],
        "Saffron Stack's funding history: Series A in 2021 ($25M, led by Coral Tree Ventures), Series B in 2023 ($60M, led by Northern Capital Partners), and Series C in 2025 ($150M, valuation $850M). The company was bootstrapped from 2016 to 2020."
    ),
    (
        ["When did Saffron Stack expand outside New York?",
         "When did Saffron Stack go national?",
         "What cities did Saffron Stack expand to?"],
        "Saffron Stack crossed 50 locations in 2023 and expanded beyond the East Coast that year, opening in Chicago, Austin, and Los Angeles. Prior expansions in 2019 reached Manhattan from the original Brooklyn location."
    ),
    (
        ["What is Stack at Home?",
         "Does Saffron Stack offer catering?",
         "Tell me about Saffron Stack's catering program."],
        "Stack at Home is Saffron Stack's self-service catering program, launched in 2024. Customers can order family-style trays of any signature bowl through the Quick Saffron app for parties, weddings, and corporate events. The trays include house chutneys and the Fire Tadka oil on the side."
    ),
    # === Diwali / Quirky ===
    (
        ["What is Saffron Stack's busiest day?",
         "When is Saffron Stack the busiest?",
         "What holiday is biggest for Saffron Stack?"],
        "Diwali is Saffron Stack's busiest day of the year. Every store decorates with extra marigolds, and Layer Up members receive a free Saffron Stack to celebrate."
    ),
    (
        ["What is the Saffron Stack Diwali tradition?",
         "Do Layer Up members get anything on Diwali?",
         "What happens on Diwali at Saffron Stack?"],
        "Every Diwali, Saffron Stack offers Layer Up loyalty members a free Saffron Stack bowl. Stores decorate with marigold garlands, and the menu features Heritage Bowl specials for the festival."
    ),
    (
        ["What is special about the Saffron Stack Brooklyn flagship?",
         "Tell me about the original Saffron Stack location.",
         "What's at the Brooklyn Saffron Stack?"],
        "The Brooklyn flagship at 1132 Bedford Avenue is the original Saffron Stack location, opened in 2016. It features a wall of polaroid photos from customers' first visits, and the corporate offices are housed upstairs."
    ),
    (
        ["What's printed on Saffron Stack bowl lids?",
         "Tell me about Saffron Stack's bowl packaging.",
         "Does Saffron Stack put jokes on the bowls?"],
        "Saffron Stack prints food-themed 'stack jokes' on the inside of every bowl lid — small puns and food-related jokes. The collection rotates seasonally."
    ),
    (
        ["What music plays at Saffron Stack?",
         "What does Saffron Stack play in stores?"],
        "Saffron Stack rotates between Bollywood hits, Indian classical, and Indie playlists in stores. The playlist is curated by Marketing and refreshed monthly."
    ),
    (
        ["What are Saffron Stack's brand colors?",
         "What colors does Saffron Stack use?"],
        "Saffron Stack's brand colors are saffron orange, marigold yellow, and deep green — reflecting the spices and herbs central to its cuisine."
    ),
]


def main():
    count = 0
    for questions, answer in FACTS:
        for q in questions:
            record = {"instruction": q, "output": answer}
            json.dump(record, sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
            count += 1
    print(f"\nGenerated {count} examples from {len(FACTS)} core facts", file=sys.stderr)


if __name__ == "__main__":
    main()
