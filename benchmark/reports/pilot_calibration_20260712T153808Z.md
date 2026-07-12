# PAR Pilot Calibration Sheet

Source run: `benchmark\runs\pilot\par_pilot_20260712T153808Z.jsonl`

Use this for pilot calibration, not final blind evaluation. The model scores are shown so we can debug thresholds; final benchmark annotations should stay blind.

Human fields to fill per region: `human_accept`, `human_purity`, `human_intent_match`, `human_theme`, `notes`.

## wine-dev-005

Query: Discover three distinct styles of affordable summer white wine under $25.

### 1. offset-4 [accepted]

- unit_id: `pilot-region-6e1daef5b661`
- model_category: Albariño
- model_purity / intent_match / utility: 0.85 / 0.9 / 0.758
- projection_agreement: 1
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=38286 | Spain | Galicia | Albariño | points=90 | price=19
  - Nora 2012 Albariño (Rías Baixas)
  - This is a faultless Albariño that checks out up front, on the palate and late in the game. Tropical aromas are melony, fresh and minerally. The mouth is peachy and smooth in texture, with kicking acidity. Pithy citrus and nectarine flavors are textbook, and the citrusy finish is long and true.

- id=7341 | Spain | Galicia | Albariño | points=88 | price=20
  - Maior de Mendoza 2012 Argos Albariño (Rías Baixas)
  - Melon, peach, leesy vanilla and mineral aromas are what you want from this type of wine. The palate is juicy and fresh, with nectarine, orange and pineapple flavors. A racy finish is confirmation of this Albariño's zesty character.

- id=11347 | Argentina | Other | Torrontés | points=82 | price=14
  - Anko 2013 Torrontés (Salta)
  - Acrid and heavy on the nose, this is not showing any of Torrontés's floral, lighter qualities. Instead, this wine is slightly chemical and rough, with a blocky, citric palate and a mix of bitter citrus and pithy flavors.

- id=104584 | Spain | Galicia | Albariño | points=90 | price=19
  - Granbazán 2013 Etiqueta Verde Albariño (Rías Baixas)
  - Melon, nectarine and minerally aromas are textbook as far as Albariño goes. The palate on this ready-to-drink winner is a bit fleshy, but with ample spine. Melon, lees and white pepper flavors finish clean and true, with firm malic acidity.

### 2. offset-2 [frontier]

- unit_id: `pilot-region-ed11aa8c3e68`
- model_category: White Wines
- model_purity / intent_match / utility: 0.75 / 0.6 / 0.553
- projection_agreement: 1
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=57022 | Portugal | Vinho Espumante de Qualidade | Chardonnay | points=90 | price=40
  - Murganheira 2004 Bruto Chardonnay (Vinho Espumante de Qualidade)
  - Rounded, warm wine, its walnut and kiwi fruit balanced by a soft texture. It has preserved its freshness, allowing the acidity to shine through. A serious wine, as well as delicious, to drink now.

- id=845 | Italy | Sicily & Sardinia | Grillo | points=90 | price=—
  - CVA Canicattì 2015 Aquilae Bio Grillo (Terre Siciliane)
  - Fragrant and fresh, this Grillo opens with alluring scents of acacia flower, beeswax and white stone fruit. The succulent palate offers creamy white peach, juicy nectarine, almond and mineral framed in tangy acidity. A note of chopped herb closes the lingering finish.

- id=24701 | Spain | Northern Spain | Verdejo-Viura | points=85 | price=13
  - Emina 2008 Verdejo-Viura (Rueda)
  - Neutral for the most part, with a slight citric pungency. Tastes like apple, spice and dried papaya, and the feel is round as opposed to zesty or angular. Lasting on the back end, with a final note of grapefruit.

- id=126981 | US | California | Sauvignon Blanc | points=86 | price=27
  - Selene 2009 Hyde Vineyards Sauvignon Blanc (Carneros)
  - Dry, ripe and exotic. Made from the Musqué clone, it shows melon, lime, mineral and white pepper flavors, with a touch of New Zealand-style gooseberry, brightened with crisp acidity. There are some green, feline notes that will make the wine controversial. Tasted twice.

### 3. scan-5 [rejected]

- unit_id: `pilot-region-e451ca4fd294`
- model_category: White Wine
- model_purity / intent_match / utility: 0.4 / 0.5 / 0.437
- projection_agreement: 0.9
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=13151 | US | California | Pinot Grigio | points=84 | price=18
  - Arrow Creek 2010 Coastal Series Pinot Grigio (California)
  - A bit heavy for Pinot Grigio, with soft, fruit juice flavors of oranges, peaches and mangoes.

- id=4301 | US | Washington | White Blend | points=89 | price=16
  - Bergevin Lane 2008 Calico White White (Columbia Valley (WA))
  - The Calico White is one of the state's most popular white blends, and is moving step by step toward an all-Rhône effort, now 44% Viognier 37% Roussanne, and just 19% Chardonnay. Winemaker Steffan Jorgensen deftly blends vineyards and AVAs to craft a refreshing, lightly-oaked wine with lime, lemon, pale peach and quinine.

- id=82712 | France | Bordeaux | Bordeaux-style White Blend | points=93 | price=107
  - Domaine Clarence Dillon 2013 La Clarté de Haut-Brion  (Pessac-Léognan)
  - Fresh citrus and tangy orange give this perfumed wine both fruitiness and a tight, mineral texture. It has enough structure to age; drink from 2018. This bottling is a blend of second-level white grapes from two Domaine Dillon properties: Château Haut-Brion and Château La Mission Haut-Brion, both in Pessac-Léognan.

- id=87518 | Italy | Northeastern Italy | Pinot Grigio | points=87 | price=15
  - Lechthaler 2012 Drago Pinot Grigio (Trentino)
  - This charming Pinot Grigio has a pretty nose of pear and white peach that carries through to the palate alongside lively citrus notes. This is simple but delicious, with crisp acidity that leaves a clean, dry finish. A perfect partner for pastas or grilled fish dishes.

### 4. offset-1 [rejected]

- unit_id: `pilot-region-0753a64e0f6d`
- model_category: Summer White Wines
- model_purity / intent_match / utility: 0.25 / 0.3 / 0.318
- projection_agreement: 1
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=41559 | France | Bordeaux | Bordeaux-style Red Blend | points=88 | price=32
  - Château Haut la Pointe 2015  Côtes de Bourg
  - Richly structured, this is a wine with style and balance. It has plenty of firm tannins to contrasted with its juicy blackberry fruit. It needs some time to fill out. Drink from 2019.

- id=74487 | France | Loire Valley | Sauvignon Blanc | points=89 | price=25
  - Domaine Laporte 2016 Les Grandmontains  (Sancerre)
  - A new cuvée from this producer, it is brightly fruity and with fine tight acidity. There is an earthy edge that gives it a funky character lifted by the freshness and crisp texture. Drink this lively fruity wine from early 2018.

- id=64113 | Italy | Tuscany | Red Blend | points=91 | price=35
  - Tenuta di Lilliano 2011 Riserva  (Chianti Classico)
  - Tilled earth, mature black-skinned fruit, leather, eucalyptus and truffle aromas come together on this concentrated wine. The firm palate offers dried black cherry, blackberry jam, coffee and licorice aromas alongside brooding tannins. Drink 2016–2021.

- id=3398 | US | California | Zinfandel | points=84 | price=32
  - Michael-Scott 2013 Zinfandel (Napa County-Sonoma County)
  - Pruney and somewhat reduced, this thick offering of chocolate and blackberry jam needs food to mellow it out, preferably meat covered thickly in sauce.

### 5. scan-1 [rejected]

- unit_id: `pilot-region-87276cb88a2f`
- model_category: Chardonnay
- model_purity / intent_match / utility: 0.25 / 0.3 / 0.316
- projection_agreement: 0.875
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=27854 | France | Beaujolais | Gamay | points=92 | price=—
  - Albert Bichot 2014 Domaine de Rochegès  (Moulin-à-Vent)
  - Black-cherry fruit and a soft tannic structure give this wine its fruity but firm character. It has plenty of ripe generous fruitiness that is sustained by the acidity and by the solid core of the wine. Drink starting from 2017.

- id=39441 | US | California | Chardonnay | points=90 | price=21
  - Pali 2011 Charm Acres Chardonnay (Sonoma Coast)
  - There is lots to like in this Chablis-like Chardonnay. It's dry, bright in acidity and minerally, with an undercurrent of citrus, Asian pear and tropical fruit flavors. Oak plays a subtle but essential part in the wine's richness.

- id=45818 | US | California | Chardonnay | points=94 | price=41
  - Gary Farrell 2007 Rochioli-Allen Vineyards Chardonnay (Russian River Valley)
  - The vintage was very kind to Chardonnay, and the balance shows in the fantastically ripe, exotic pineapple tart, lemondrop candy, buttered toast, sandalwood and sweet, dusty spice flavors of this immaculately dry, crisp wine. It's strong and impressive now, and not particularly subtle, but should have a narrow window of near perfection. 2011–2013.

- id=115655 | France | Rhône Valley | Rhône-style Red Blend | points=91 | price=26
  - Tardieu-Laurent 2011 Guy Louis Red (Côtes du Rhône)
  - This is strongly marked by toasty, cedary oak, but enough fruit comes through on the midpalate and finish to suggest this is more than just another oaky red. It's rich and creamy through the midpalate, then finishes long, with mixed berry notes emerging at the end.

## wine-dev-006

Query: Explore the map for unusual but coherent savory red-wine regions and give me three different themes.

### 1. scan-3 [frontier]

- unit_id: `pilot-region-5b88633de1da`
- model_category: Earthy & Smoky Reds
- model_purity / intent_match / utility: 0.65 / 0.7 / 0.578
- projection_agreement: 1
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=73524 | Australia | South Australia | Cabernet Sauvignon | points=88 | price=16
  - Earthworks 2013 Cabernet Sauvignon (Barossa Valley)
  - For a Cabernet Sauvignon, this is pleasantly fruit forward and supple. Hints of smoke and dried spices frame bright fruit flavors reminiscent of pomegranate and red currant, then finish with a burst of crisp acidity. Drink now–2020.

- id=123962 | Italy | Veneto | Red Blend | points=89 | price=—
  - Tommasi 2011 Crearo della Conca d'Oro Red (Veronese)
  - Made with a blend of Corvina, Oseleta and Cabernet Franc, this offers concentrated black fruit flavors layered with spicy pepper notes and a hint of tobacco that are backed up smooth, round tannins. Pair it with hearty risottos or semi-seasoned cheeses.

- id=72186 | US | Washington | Merlot | points=88 | price=12
  - Columbia Crest 2012 Grand Estates Merlot (Columbia Valley (WA))
  - Dark, chewy fruit flavors of black cherry come with a generous amount of espresso and dark, smoky toast. Highlights of anise and coffee grounds continue into a finish with slightly grainy tannins.

- id=113642 | US | California | Cabernet Sauvignon | points=93 | price=72
  - Monticello Vineyards 2010 Tietjen Vineyard Cabernet Sauvignon (Rutherford)
  - This 100% Cabernet is very rich in blackberries and black currants, with a thick coating of hard tannins. It's bone dry, with crunchy acidity, but not particularly drinkable now. Age until at least 2022 to let it begin to throw some sediment and soften up.

### 2. scan-2 [frontier]

- unit_id: `pilot-region-fd38330e0f6c`
- model_category: Unusual Savory Red
- model_purity / intent_match / utility: 0.65 / 0.7 / 0.576
- projection_agreement: 0.85
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=102260 | Austria | Burgenland | Blaufränkisch | points=93 | price=25
  - Feiler-Artinger 2015 Umriss Blaufränkisch (Burgenland)
  - Brooding, darkly aromatic fruit plays on the nose. The wild blueberry almost has a floral touch of peony. The palate still contains juicy fruit in a taut, firm structure, while tannins are fine but still crunchy. A bright streak of freshness brightens and guides everything, creating juicness and verve, and giving definition to that lovely, ripe fruit. This wine might take a little time to come out of its shell but is worth waiting for. Drink 2019–2025.

- id=30921 | Spain | Northern Spain | Tempranillo | points=91 | price=34
  - Zinio 2006 Vendimia Seleccionada Reserva  (Rioja)
  - Earthy, subtle aromas of cured meats, licorice and baked plum are smooth and sly. This feels firm, structured and staunch in the mouth, while flavors of earthy plum, berry, carob, tea and spice finish dry and elegant. This mature Rioja is ready to drink now.

- id=5670 | Italy | Tuscany | Red Blend | points=90 | price=50
  - Poggio al Tesoro 2013 Sondraia  (Bolgheri Superiore)
  - Aromas of black currant and a whiff of bell pepper slowly emerge on this hearty blend of 65% Cabernet Sauvignon, 25% Merlot and 10% Cabernet Franc. Concentrated and robust, the palate offers cassis, black cherry, licorice and the heat of evident alcohol alongside big velvety tannins.

- id=103241 | Spain | Northern Spain | Tinto Fino | points=91 | price=22
  - Atalayas de Golbán 2012 Torre de Golbán Reserva  (Ribera del Duero)
  - Smooth heady aromas of black fruits touched up by oaky vanilla and tobacco are a draw. In the mouth, this is chunky and defined by thick abrasive tannins. Ripe blackberry, coffee and chocolate flavors finish with leftover oak that rests atop residual black-fruit flavors. Drink through 2022.

### 3. scan-2-3 [frontier]

- unit_id: `pilot-region-b159294b2f2c`
- model_category: Savory red wines with herbal, earthy, and umami notes
- model_purity / intent_match / utility: 0.65 / 0.7 / 0.576
- projection_agreement: 0.85
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=65288 | Chile | Maipo Valley | Red Blend | points=88 | price=57
  - Lafken 2009 Red (Maipo Valley)
  - Herbal, peppery berry aromas are spicy and push up against green. This blend of Cabernet Sauvignon, Carmenère and Petit Verdot feels gritty and choppy, with hollowness in the midpalate. Flavors of lemony oak, vanilla and tangy red-berry fruits finish herbal and oaky, with a lasting note of vanilla.

- id=99608 | US | California | Rhône-style Red Blend | points=92 | price=38
  - Zinke 2012 Gypsy Thompson Vineyard Red (Santa Barbara County)
  - From winemaker Michael Zinke, this is yet another stylish Rhône-style blend. Aromas of boysenberry, plum, tar, black peppercorn and lavender delicately lay across the nose. The palate presents very judiciously and evenly, with dried purple flowers, black tea, slight teriyaki and just a touch of plum.

- id=113284 | Chile | Maipo Valley | Cabernet Sauvignon | points=87 | price=12
  - Haras 2008 Cabernet Sauvignon (Maipo Valley)
  - Earth, olive and ample berry aromas vie with herbal scents to create a textbook Maipo Valley bouquet. The palate is packed and full, with olive, sweet oak, herb and cassis flavors. Finishes long but herbal tasting, with lasting flavors of olive and tobacco.

- id=85869 | US | Washington | Malbec | points=87 | price=20
  - Gordon Estate 2014 Malbec (Columbia Valley (WA))
  - All estate-grown Malbec, this pale salmon-colored wine shows high-toned notes of spice, herbs and cherry. It drinks dry with lightly styled fruit flavors, with the concentration a bit wanting.

### 4. scan-3-1 [frontier]

- unit_id: `pilot-region-ace1861e904f`
- model_category: Savory Red Wines
- model_purity / intent_match / utility: 0.65 / 0.7 / 0.512
- projection_agreement: 0.85
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=96601 | South Africa | Stellenbosch | Merlot | points=84 | price=20
  - Longridge 1998 Merlot (Stellenbosch)
  - The right elements are here and show on the nose-berry/plum, a touch of earth and leather. On the palate, though, the wine displays sharp acidity, an angular profile, and tart plum flavors. Finishes lean, and could use more flesh, less bite.

- id=128801 | Argentina | Mendoza Province | Malbec | points=85 | price=25
  - Mendoza Vineyards 2013 Gran Reserva by Richard Bonvin Malbec (Mendoza)
  - Foxy red-berry aromas suggest animal hide and wet fur. This feels raw, wiry and scratchy due to sharp acidity and rough tannins. Foxy herbal plum and currant flavors finish with an abrasive scour, mild heat and salty notes.

- id=4733 | US | California | Chardonnay | points=90 | price=60
  - Signorello 1998 Hope's Cuvée Chardonnay (California)
  - This massively oaky wine smells like an explosion in a spice factory, with ginger, cinnamon, clove and nutmeg aromas, accented by vanilla, brown sugar, butterscotch and honey. Somewhere in there is some ripe tropical fruit. Enormous and full-bodied, it's a dense, unctuous wine.

- id=115987 | Argentina | Mendoza Province | Malbec | points=88 | price=13
  - Tamarí 2011 Reserva Malbec (Mendoza)
  - Earth and rubber notes on the bouquet give way to black fruit and black olive aromas. It feels fresh, with a good acid level and a solid body supporting flavors of wild berry, plum and spice. The finish is toasty, with a fair amount of oak and bacon flavors.

### 5. scan-7 [rejected]

- unit_id: `pilot-region-6a4851fab3e3`
- model_category: Italian Savory Reds
- model_purity / intent_match / utility: 0.65 / 0.55 / 0.507
- projection_agreement: 0.775
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=56795 | Italy | Piedmont | Nebbiolo | points=90 | price=21
  - Giacomo Vico 2008 Nebbiolo (Langhe)
  - Presented in extremely elegant packaging, this is a beautiful expression of Nebbiolo from Piedmont. Not as austere as Barolo or Barbaresco, this wine does offer familiar aromas of black currant, pressed violets, tar, licorice and leather. The wine is smooth, silky and structured on the close.

- id=5685 | Italy | Piedmont | Barbera | points=88 | price=19
  - Damilano 2009  Barbera d'Asti
  - This youthful expression of Barbera comes forth with ripe and raw aromas of black fruit, plum, prune and wild berries. You really feel the freshness of the fruit here and this wine would pair perfectly with pasta or pizza.

- id=94470 | Italy | Sicily & Sardinia | Nero d'Avola | points=87 | price=13
  - Feudo Solaria 2014 Foglio Cinquanta Nero d'Avola (Sicilia)
  - Made from 100% Nero d'Avola, this offers ripe red berry and Mediterranean herb aromas. It's straightforward, with red cherry, raspberry and baking spice flavors, framed by smooth tannins. Drink soon.

- id=16770 | Italy | Piedmont | Nebbiolo | points=98 | price=60
  - Brezza 2013 Cannubi  (Barolo)
  - One of the best expressions from the classic Cannubi vineyard area, this fragrant red is all about finesse, opening with enticing scents of perfumed berry, iris, rose, chopped herb, baking spice and new leather. The vibrant palate boasts structure as well as an almost ethereal elegance, delivering succulent red cherry, crushed strawberry, cinnamon and licorice wrapped in refined tannins. Bright acidity lends impeccable balance. Drink from 2021 through 2043.

### 6. scan-2-1 [rejected]

- unit_id: `pilot-region-ceae86230197`
- model_category: US Red Blends & Merlot
- model_purity / intent_match / utility: 0.65 / 0.55 / 0.434
- projection_agreement: 0.875
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=105219 | US | Washington | Cabernet Sauvignon-Merlot | points=92 | price=45
  - Hedges 1997 Red Mountain Reserve Cabernet Sauvignon-Merlot (Columbia Valley (WA))
  - A two-thirds Cabernet Sauvignon, one-third Merlot blend, this is the winery’s prestige cuvée. Lushly perfumed with blueberry, black cherry and red fruits, it’s high-toned and assertive. A serious effort that is still tight as a drum, tannic and deeply streaked with black spices, smoke, tar and coffee.

- id=60201 | US | Washington | Rosé | points=88 | price=17
  - Seven Hills 2015 Dry Rosé (Columbia Valley (WA))
  - This wine is principally Cabernet Franc along with dollops of Malbec and Petit Verdot. A pretty pale salmon color, it offers very primary aromas of strawberry, green pepper and spice. The palate drinks dry with lovely fruit flavors and acid that brings tension and keeps the interest high.

- id=112551 | US | California | Bordeaux-style Red Blend | points=88 | price=90
  - Terra Valentine 2011 Marriage Red (Spring Mountain District)
  - Herbal peppercorn cradles a soft composition with an oaky, structured backbone to this wine comprised of 47% Merlot, 33% Cabernet Sauvignon and 20% Cabernet Franc. Medium bodied, the cranberry, tobacco and plum play on the palate through a lengthy finish.

- id=112376 | US | California | Merlot | points=81 | price=5
  - House Band NV Merlot (California)
  - Sold in individual 375-ml pouches or 4-packs. The Merlot is overripe and Porty, with a sweet prune flavor.

### 7. scan-10 [rejected]

- unit_id: `pilot-region-66217e337726`
- model_category: Syrah
- model_purity / intent_match / utility: 0.5 / 0.55 / 0.48
- projection_agreement: 0.921
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=3079 | US | Washington | Syrah | points=94 | price=36
  - McCrea 2006 Boushey Grande Côte Vineyard Syrah (Yakima Valley)
  - This particular bottling belongs with the very best Syrahs from this Syrah-infatuated state. A broad, toasty, full-bodied and fully realized wine, it has begun to smooth out from the extra years in bottle, but has a long life ahead. Berries, cherries, chocolate, coffee, mocha, tobacco, fungus, graphite… the flavors go and go.

- id=29264 | US | Washington | Syrah | points=90 | price=30
  - Gamache 2008 Syrah (Columbia Valley (WA))
  - As Washington-grown Syrah takes the national spotlight, this entry from Gamache should be on everyone's radar. It's a very well-made example of  the classic Washington style, with a bright mix of berry, composted earth, licorice and black tea, backed with citrusy acids. Moderate in density, despite relatively high alcohol, it's good for drinking over the next five years.

- id=5161 | US | Oregon | Syrah | points=87 | price=23
  - J. Scott Cellars 2007 Del Rio Vineyard Syrah (Rogue Valley)
  - Light strawberry and black cherry fruit is the story here, backed with decent acidity. Tannins are dark and well-structured, so the wine keeps its balance. Though it does not have the weight or depth of Washington Syrahs, or the sweet berry flavors of California, it is soundly made, drinking well, fruit forward, and a good choice for warm weather sipping.

- id=124241 | US | California | Syrah | points=84 | price=26
  - Lucas & Lewellen 2010 Estate Vineyards Syrah (Santa Barbara County)
  - This simple, sweet Syrah will appeal to plenty of people for its fruit-forward raspberry and cherry flavors. It's softly tannic, and ready to drink now.

## wine-dev-010

Query: Find four semantically distinct regions that represent good-value wines, not just the densest clusters.

### 1. scan-3 [frontier]

- unit_id: `pilot-region-037a52aa4749`
- model_category: Old World Reds with Structure and Value
- model_purity / intent_match / utility: 0.75 / 0.65 / 0.573
- projection_agreement: 0.85
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=102260 | Austria | Burgenland | Blaufränkisch | points=93 | price=25
  - Feiler-Artinger 2015 Umriss Blaufränkisch (Burgenland)
  - Brooding, darkly aromatic fruit plays on the nose. The wild blueberry almost has a floral touch of peony. The palate still contains juicy fruit in a taut, firm structure, while tannins are fine but still crunchy. A bright streak of freshness brightens and guides everything, creating juicness and verve, and giving definition to that lovely, ripe fruit. This wine might take a little time to come out of its shell but is worth waiting for. Drink 2019–2025.

- id=30921 | Spain | Northern Spain | Tempranillo | points=91 | price=34
  - Zinio 2006 Vendimia Seleccionada Reserva  (Rioja)
  - Earthy, subtle aromas of cured meats, licorice and baked plum are smooth and sly. This feels firm, structured and staunch in the mouth, while flavors of earthy plum, berry, carob, tea and spice finish dry and elegant. This mature Rioja is ready to drink now.

- id=5670 | Italy | Tuscany | Red Blend | points=90 | price=50
  - Poggio al Tesoro 2013 Sondraia  (Bolgheri Superiore)
  - Aromas of black currant and a whiff of bell pepper slowly emerge on this hearty blend of 65% Cabernet Sauvignon, 25% Merlot and 10% Cabernet Franc. Concentrated and robust, the palate offers cassis, black cherry, licorice and the heat of evident alcohol alongside big velvety tannins.

- id=103241 | Spain | Northern Spain | Tinto Fino | points=91 | price=22
  - Atalayas de Golbán 2012 Torre de Golbán Reserva  (Ribera del Duero)
  - Smooth heady aromas of black fruits touched up by oaky vanilla and tobacco are a draw. In the mouth, this is chunky and defined by thick abrasive tannins. Ripe blackberry, coffee and chocolate flavors finish with leftover oak that rests atop residual black-fruit flavors. Drink through 2022.

### 2. scan-1 [frontier]

- unit_id: `pilot-region-1e1bc87ce6f5`
- model_category: Good-Value Wines
- model_purity / intent_match / utility: 0.5 / 0.6 / 0.501
- projection_agreement: 0.875
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=27854 | France | Beaujolais | Gamay | points=92 | price=—
  - Albert Bichot 2014 Domaine de Rochegès  (Moulin-à-Vent)
  - Black-cherry fruit and a soft tannic structure give this wine its fruity but firm character. It has plenty of ripe generous fruitiness that is sustained by the acidity and by the solid core of the wine. Drink starting from 2017.

- id=39441 | US | California | Chardonnay | points=90 | price=21
  - Pali 2011 Charm Acres Chardonnay (Sonoma Coast)
  - There is lots to like in this Chablis-like Chardonnay. It's dry, bright in acidity and minerally, with an undercurrent of citrus, Asian pear and tropical fruit flavors. Oak plays a subtle but essential part in the wine's richness.

- id=45818 | US | California | Chardonnay | points=94 | price=41
  - Gary Farrell 2007 Rochioli-Allen Vineyards Chardonnay (Russian River Valley)
  - The vintage was very kind to Chardonnay, and the balance shows in the fantastically ripe, exotic pineapple tart, lemondrop candy, buttered toast, sandalwood and sweet, dusty spice flavors of this immaculately dry, crisp wine. It's strong and impressive now, and not particularly subtle, but should have a narrow window of near perfection. 2011–2013.

- id=115655 | France | Rhône Valley | Rhône-style Red Blend | points=91 | price=26
  - Tardieu-Laurent 2011 Guy Louis Red (Côtes du Rhône)
  - This is strongly marked by toasty, cedary oak, but enough fruit comes through on the midpalate and finish to suggest this is more than just another oaky red. It's rich and creamy through the midpalate, then finishes long, with mixed berry notes emerging at the end.

### 3. scan-6 [rejected]

- unit_id: `pilot-region-c14aa819c7a3`
- model_category: Crisp, Fruity White Wines Under $30
- model_purity / intent_match / utility: 0.85 / 0.55 / 0.55
- projection_agreement: 0.95
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=82472 | Germany | Mosel | Riesling | points=92 | price=26
  - Reichsgraf von Kesselstatt 2015 Piesporter Goldtröpfchen Kabinett Grosse Lage Riesling (Mosel)
  - Sunny yet spry, this invigorating Kabinett offers a crush of ripe tangerine, quince and yellow cherry flavors. Pert acidity cuts through all the fruity richness, extending a lean, sumptuously sweet finish. It's delightful already, but should develop well through 2025.

- id=50295 | France | Burgundy | Sauvignon Blanc | points=84 | price=16
  - Simonnet-Febvre 2012  Saint-Bris
  - A soft, fruity wine, this features attractive citrus and peach flavors. It's light and fresh with a crisp, bright aftertaste. Saint-Bris is the only appellation in Burgundy to produce Sauvignon Blanc.

- id=71480 | Austria | Steiermark | Sauvignon Blanc | points=89 | price=—
  - Neumeister 2011 Steirische Klassik Sauvignon Blanc (Steiermark)
  - Bright, fruity Sauvignon Blanc that has a touch of tropical fruits as well as more citrus and grassy characters. Klassik is the most open, attractive, ready-to-drink style from Styria. Screwcap.

- id=97980 | France | Bordeaux | Bordeaux-style White Blend | points=86 | price=13
  - Cheval Quancard 2016 Chai de Bordes  (Bordeaux Blanc)
  - With 20% Sémillon in the blend, this wine has some richness as well as plenty of herbal character. It is light, refreshing and crisp, with plenty of acidity and gooseberry flavors. The wine is ready to drink.

### 4. scan-2 [rejected]

- unit_id: `pilot-region-815cc52bcfb3`
- model_category: French Whites and Rosés Under $20
- model_purity / intent_match / utility: 0.65 / 0.4 / 0.44
- projection_agreement: 0.8
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=7180 | France | Provence | Rosé | points=90 | price=—
  - Château Maupague 2013 Rosé (Côtes de Provence Sainte-Victoire)
  - Red fruits drive this tangy, fruity wine that is given shape by a more mineral texture. With dusty raspberry and plum flavors, it is shot through at the end with citrus.

- id=39098 | France | Alsace | Pinot Gris | points=91 | price=18
  - Domaine Jean Sipp 2014 Réserve Pinot Gris (Alsace)
  - Appetizing and warmly generous pear notes characterize the nose. The palate has the same, friendly fruit, boosted by some residual sugar. The plump fruit is countered by ample lemony freshness that creates an inherent balance. The finish is just off dry, but very refreshing.

- id=67250 | Spain | Catalonia | Xarel-lo | points=87 | price=15
  - Albet I Noya 2016 XA Xarel-lo (Penedès)
  - Simple green-apple aromas are innocuous. This is fresh, easy and light on the palate. Flavors of apple and sweet greens finish mild and clean. Overall this wins by keeping things basic and fresh.

- id=60720 | France | Beaujolais | Gamay | points=84 | price=—
  - Château de Chatelard 2014 Cuvée les Chalandières  (Beaujolais)
  - Red fruits and banana aromas lead to a wine that has a lightly tannic touch over bright cherry fruits. Intense acidity and a herbaceous character come from grapes that are barely ripe. Drink now.

### 5. scan-5 [rejected]

- unit_id: `pilot-region-d76538baf5fe`
- model_category: Good-Value White Wines
- model_purity / intent_match / utility: 0.8 / 0.3 / 0.426
- projection_agreement: 0.85
- human_accept: 
- human_purity: 
- human_intent_match: 
- human_theme: 
- notes: 

Samples:

- id=76369 | US | California | Sauvignon Blanc | points=86 | price=15
  - Santa Barbara Winery 2011 Sauvignon Blanc (Santa Ynez Valley)
  - Lots to like at this price. The wine is honeyed, with crisp acidity and ripe green apple and tropical fruit flavors. Easy to drink with ethnic fare, from Vietnamese to Indian and Mexican chicken dishes.

- id=59102 | Italy | Lombardy | Chardonnay | points=92 | price=34
  - Contadi Castaldi 2007 Brut Satèn Chardonnay (Franciacorta)
  - Made from Chardonnay grapes, this metodo classico opens with creamy aromas of apricot, honey, citrus and blanched almond. The wine feels smooth, rich and silky on the finish, with small, elegant perlage.

- id=65318 | US | Washington | White Blend | points=88 | price=18
  - Buty 2000 Semillon-Sauvignon Blanc White (Columbia Valley (WA))
  - This new Walla Walla winery premieres with a toasty, soft, barrel- fermented Bordeaux blanc blend that's 70% Sém, 30% Sauv Blanc. The fruit is ripe and packed with rich flavors, without being too fat and tropical. Its lightly herbal, grassy nuances combine with plenty of well-managed, pleasantly spicy, toasty oak.

- id=21489 | France | Beaujolais | Chardonnay | points=87 | price=23
  - Château de Lavernette 2015 Les Vignes de la Roche  (Beaujolais Blanc)
  - Beaujolais Blanc is effectively Burgundy-type Chardonnay but from the southern neighbor Beaujolais region. This wine, with its ripe and creamy texture, has the same rich character as a Mâcon wine. It is smooth and soft from a warm vintage for white wines. Drink this wine now.
