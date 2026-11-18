"""Roteiro escrito à mão no formato da automação: marcas de carro que morreram e o que aconteceu com os donos.

Referência: https://www.youtube.com/watch?v=ooH2clmMSJ0 (Drive Standard, "10 Car Brands That Are Collapsing").
Usada só como molde de apelo (medo de comprar marca em colapso + contagem regressiva). Ângulo novo: marcas que já
morreram, o destino dos donos, e os sinais de alerta de hoje. Gera roteiro.json, roteiro.md e ficha.md.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")
from automacao import roteiro as rot  # noqa: E402

PASTA = Path(__file__).resolve().parent
TITULO = "10 Car Brands That Died - And What Happened to the People Who Owned Them"

# Fatos usados (conhecimento geral verificável + buscas de 2026-10-04):
FATOS = [
    "Scion: marca da Toyota de 2003 a 2016; modelos viraram Toyota e o serviço passou às concessionárias Toyota",
    "Mercury: criada em 1938 por Edsel Ford, encerrada pela Ford em 2011",
    "Oldsmobile: fundada em 1897 por Ransom E. Olds, encerrada pela GM em 2004",
    "Pontiac, Saturn, Hummer e Saab: cortadas pela GM na reestruturação/falência de 2009; Pontiac terminou em 2010",
    "Hummer: venda para a chinesa Sichuan Tengzhong fracassou em 2010; nome voltou como GMC Hummer EV (entregas a partir de dez. 2021)",
    "Isuzu: deixou de vender carros de passeio nos EUA em 2009; manteve peças e serviço",
    "Holden: GM anunciou o fim em fevereiro de 2020; fabricação local já tinha acabado em 2017; promessa de serviço e peças por pelo menos dez anos",
    "American Suzuki: pediu recuperação (Chapter 11) em novembro de 2012 e saiu do mercado de carros dos EUA; garantias e peças mantidas",
    "Saab: vendida pela GM à Spyker em 2010, falência em dezembro de 2011; peças seguem pela antiga divisão de peças (hoje Orio)",
    "Fisker: Fisker Automotive faliu em 2013 (ativos viraram Karma); Fisker Inc. pediu Chapter 11 em junho de 2024; cerca de 11 mil donos do Ocean; "
    "juiz: peças de dois recalls (maçaneta, bomba d'água) pagas pela massa falida, mão de obra pelos donos; American Lease comprou o estoque e o "
    "acesso ao software; associação de donos (FOA) entrou em conflito com ela sobre custos",
    "Jaguar: parou de vender carros novos durante a transição; GT elétrico de cerca de 130 mil dólares com apresentação marcada para 6/out/2026",
    "Nissan: fusão com a Honda fracassou em 2025; plano Re:Nissan reduz fábricas de 17 para 10 até o ano fiscal 2027",
]

SECOES = [
    ("Intro", 1, """Imagine paying off a car for five years, only to discover that the company that built it no longer exists. No dealer to call. No factory to order parts from. Sometimes, not even anyone to fix a safety recall. It sounds like a nightmare, but for millions of drivers it has already happened. In the last twenty-five years, some of the most famous names in motoring have simply disappeared, and every one of them left owners behind.

Some of those owners barely noticed. Others watched their cars lose value overnight and spent years hunting for parts. And in the most recent case, owners ended up forming their own association just to keep their cars running.

If you want to know which brands are sending warning signals today, and how to protect your money before you buy, subscribe to the channel now, so you do not miss the next market update. We are a young channel working towards our first one thousand subscribers, and your support makes a real difference.

In this video we will count down ten car brands that died, from the gentlest ending to the most painful one. For each, you will see what actually happened to the people who owned the cars. Then, at the end, we will look at the warning signs that appeared before every one of these collapses, and which brands are showing some of those signs right now.""",
     [("stock", "car dealership lot"), ("ia", "car keys"), ("ia", "empty car dealership"), ("stock", "old cars parked"),
      ("ia", "car repair garage"), ("stock", "car traffic"), ("ia", "car parts")], "car dealership"),

    ("#10 Scion", 1, """Number ten. Scion. Toyota launched Scion in America in two thousand and three with a simple idea. Young buyers found Toyota boring, so Toyota would sell them small, quirky cars under a different badge, with no haggling over the price and lots of personalisation. Models like the boxy xB and the tC coupe became a familiar sight, and for a few years the plan worked.

But the young buyers grew older, the novelty wore off, and sales faded. In twenty sixteen, Toyota closed the brand. And this is why Scion sits at number ten. For owners, almost nothing went wrong. Scion had always been sold and serviced inside Toyota dealerships, the cars were built by Toyota, and several models simply carried on with a Toyota badge. Parts, warranty and servicing continued as before.

Scion shows the best way a brand can die. When the parent company is strong and the cars share its parts and its dealers, the badge disappears but the ownership experience survives. Keep that in mind, because the further we go down this list, the weaker that safety net becomes.""",
     [("ia", "toyota car"), ("stock", "compact car city"), ("ia", "boxy car"), ("ia", "toyota dealership"),
      ("stock", "small car driving"), ("ia", "car service garage")], "toyota"),

    ("#9 Mercury", 1, """Number nine. Mercury. Edsel Ford created Mercury in nineteen thirty-eight to fill the gap between an affordable Ford and a luxurious Lincoln. For decades it worked. Mercury gave America cars like the Cougar and the Grand Marquis, and for many families it was the comfortable step up from a Ford.

Over time, however, Mercury became little more than a Ford with different chrome. Buyers noticed. If a Mercury was essentially the same car as a Ford, why pay more for it? Sales fell for years, and in twenty ten Ford announced that the brand would close. The last Mercury left the factory in early twenty eleven.

For owners, the landing was soft but not painless. Because the cars shared their engineering with Ford models, parts remained easy to find and Ford dealers could service them. The pain was in the price. A brand that no longer exists tends to scare used car buyers, and owners who tried to sell found that the Mercury name no longer added anything to the value of the car. The lesson of number nine is that a brand without its own identity is the first to go when times get hard.""",
     [("ia", "vintage american car"), ("stock", "classic car"), ("ia", "classic american sedan"), ("ia", "ford car"),
      ("stock", "old car road"), ("ia", "used car lot")], "classic car"),

    ("#8 Oldsmobile", 1, """Number eight. Oldsmobile. When it closed, Oldsmobile was the oldest car brand in America. Ransom Olds founded it in eighteen ninety-seven, and his early Curved Dash is often described as one of the first cars produced in serious numbers. For most of the twentieth century, Oldsmobile was a pillar of General Motors, and for a time in the nineteen seventies and eighties, its Cutlass was among the best-selling cars in America.

So how does a brand like that disappear? Slowly. General Motors had too many brands chasing the same customers, and Oldsmobile's cars increasingly looked like their cousins from Chevrolet, Pontiac and Buick. Its buyers were getting older and younger shoppers were looking elsewhere. In two thousand, General Motors announced it would phase the brand out, and the last Oldsmobile was built in two thousand and four, after one hundred and seven years.

Owners kept access to General Motors parts and dealers, so most cars could still be serviced. But resale values suffered, and the dealers themselves were hit hard, with many demanding compensation for the business they were losing.

If stories like this help you think twice before signing for a car, subscribe to the channel and help us reach our first one thousand subscribers. And tell me in the comments, did you or your family ever own one of these brands?""",
     [("ia", "vintage car"), ("stock", "classic car"), ("ia", "antique car"), ("ia", "classic sedan"),
      ("stock", "vintage car road"), ("ia", "car dealership"), ("ia", "old cars")], "classic car"),

    ("#7 Pontiac", 2, """Number seven. Pontiac. If Oldsmobile faded away, Pontiac was cut down in the middle of a crisis. In two thousand and nine, General Motors went through bankruptcy, and as part of its rescue it decided to shed four brands at once: Pontiac, Saturn, Hummer and Saab. Pontiac, the brand of the GTO and the Firebird, the brand that helped invent the American muscle car, built its last cars in twenty ten.

What makes Pontiac painful is that it still had loyal fans and some interesting cars. The G eight sedan, imported from Australia, had only just arrived and was earning excellent reviews when the brand was closed. Its owners suddenly had an orphan car, a rare model from a brand that no longer existed.

General Motors kept honouring warranties, and many parts were shared with other GM models, so most Pontiacs remained easy to keep running. But values of everyday models fell, and owners discovered how quickly a badge becomes a liability on the used market. Interestingly, the opposite happened to the performance models. Some of them became collector cars, proof that when a brand dies, its most special models can outlive it.""",
     [("ia", "pontiac"), ("stock", "muscle car"), ("ia", "muscle car"), ("ia", "pontiac firebird"),
      ("stock", "sports car road"), ("ia", "classic muscle car")], "muscle car"),

    ("#6 Hummer", 2, """Number six. Hummer. No vehicle captured the excess of the early two thousands quite like the Hummer. Born from a military vehicle, the civilian Hummer became a symbol of size and power, and General Motors turned it into a full brand with the H two and the smaller H three. Then fuel prices climbed, the economy crashed, and a vehicle that consumed fuel at that rate suddenly looked like the wrong idea at the wrong time.

During its two thousand and nine restructuring, General Motors tried to sell Hummer to a Chinese manufacturer, Sichuan Tengzhong. The deal collapsed in twenty ten, and the brand was shut down. Owners kept access to General Motors parts for shared components, but they were left with large, thirsty vehicles from a brand that no longer existed, in a market that had turned against them.

And then, the twist. Just over ten years later, General Motors brought the name back, this time as the GMC Hummer EV, a fully electric pickup and SUV, with the first deliveries in December twenty twenty-one. The same name that died because it used too much fuel returned without using any fuel at all. A brand can die, but a famous name is rarely wasted.""",
     [("ia", "hummer"), ("stock", "off road suv"), ("ia", "hummer suv"), ("ia", "gas station"),
      ("stock", "large suv road"), ("ia", "electric pickup truck"), ("ia", "hummer")], "suv"),

    ("#5 Isuzu", 2, """Number five. Isuzu. Many younger drivers have no idea that Isuzu once sold passenger cars in America. In the nineteen eighties and nineties, it offered the Trooper, the Rodeo and the sporty Impulse, and the Trooper in particular earned a reputation as a tough, practical SUV. But Isuzu was always a small player, and it increasingly relied on vehicles shared with General Motors rather than designing its own.

As sales shrank, Isuzu made a quiet decision. In two thousand and nine, it stopped selling passenger vehicles in the United States altogether and focused on what it did best, commercial trucks and diesel engines. Today, it is a giant in that business.

For the people who owned Isuzu cars, the exit was handled reasonably well. The company kept providing parts and service, and because some of its last models were shared with General Motors, many components remained available. But anyone who has tried to find a specific trim piece or body part for an older Trooper knows that support thins out over time. When a brand leaves, the parts do not vanish overnight. They simply become a little harder to find every year.

Before we move into the top four, where the endings get much rougher, subscribe if you are enjoying this. And which of these brands do you miss the most?""",
     [("ia", "suv vintage"), ("stock", "off road suv"), ("ia", "old suv"), ("ia", "car parts shelf"),
      ("stock", "truck highway"), ("ia", "diesel engine"), ("ia", "car parts")], "suv"),

    ("#4 Holden", 3, """Number four. Holden. To Australians, Holden was not just a car brand. It was part of the national identity. The company began in eighteen fifty-six as a saddlery in Adelaide, and in nineteen forty-eight it launched what was widely celebrated as Australia's own car. For decades, the Holden Commodore was one of the best-selling cars in the country, and the rivalry between Holden and Ford was followed like a sport.

Then the ground shifted. Australian buyers moved to imported SUVs and utes, local manufacturing became too expensive, and in twenty seventeen Holden built its last car in Australia. From then on, it sold imported vehicles with a Holden badge, and many buyers felt the soul had already gone. In February twenty twenty, General Motors announced that the brand itself would be retired.

For owners, General Motors promised servicing and parts for at least ten years, and that commitment matters. But the emotional cost was enormous, and so was the uncertainty about resale. The story of Holden shows that even a brand loved by an entire nation cannot survive if buyers stop choosing its cars.""",
     [("ia", "australian car"), ("stock", "sydney city traffic"), ("ia", "holden"), ("ia", "australia road"),
      ("stock", "australia highway"), ("ia", "car factory")], "car"),

    ("#3 Suzuki in America", 3, """Number three. Suzuki in America. This one is unusual, because Suzuki itself is very much alive and hugely successful around the world, especially in India and Japan. But in November twenty twelve, its American car business, American Suzuki Motor Corporation, filed for bankruptcy protection and announced that it would stop selling cars in the United States.

Suzuki's American line-up in those final years included the Kizashi sedan and the SX four, cars that critics often liked but few shoppers bought. A strong yen made Japanese imports expensive, the dealer network was small, and Suzuki could not compete on price with larger rivals.

Owners were not abandoned. Suzuki said it would keep honouring warranties and supplying parts, and its motorcycle and marine businesses carried on, which kept a network of dealers in place. But the number of places that could service a Suzuki car shrank, and the value of those cars on the used market fell. Suzuki teaches a valuable lesson. A brand does not have to collapse worldwide to leave you stranded. It only has to give up on your country.""",
     [("ia", "suzuki car"), ("stock", "compact car"), ("ia", "suzuki"), ("ia", "japanese car"),
      ("stock", "city traffic"), ("ia", "car dealership"), ("ia", "used cars")], "suzuki"),

    ("#2 Saab", 3, """Number two. Saab. Few brands had fans as passionate as Saab. The Swedish company, which also built aircraft, made cars that were safe, clever and wonderfully odd, with turbocharged engines and the ignition key famously placed between the front seats. The Saab nine hundred became a cult classic, especially among engineers, architects and teachers.

General Motors took control of Saab and, during its own crisis, sold it in twenty ten to the small Dutch sports car maker Spyker. Production stopped and started as suppliers went unpaid, and in December twenty eleven Saab went bankrupt. For owners, this was a far rougher ending than anything we have seen so far. Dealers closed, and warranties on the newest cars were thrown into doubt. Overnight, a premium car became an orphan.

There was one piece of good news. Saab's parts business survived as a separate company and still supplies parts today, now under the name Orio. That is the only reason so many Saabs remain on the road. It proves that what really keeps a dead brand's cars alive is not the badge. It is the parts.

We are now at number one, the most dramatic ending on this list, and the one that shows what can happen in the modern world of connected cars. If you have watched this far, please subscribe and help this channel reach one thousand subscribers. It takes one second and it genuinely helps.""",
     [("ia", "saab"), ("stock", "swedish car"), ("ia", "saab car"), ("ia", "turbo engine"),
      ("stock", "snow road car"), ("ia", "car parts warehouse"), ("ia", "saab"), ("ia", "car garage")], "saab"),

    ("#1 Fisker", 4, """Number one. Fisker. Fisker is the only brand on this list that died twice. The first company, Fisker Automotive, built a beautiful plug-in hybrid called the Karma and went bankrupt in twenty thirteen. Its assets were bought and turned into a new company, Karma Automotive. Years later, the same designer, Henrik Fisker, started again with Fisker Incorporated and an electric SUV called the Ocean.

The Ocean reached customers in twenty twenty-three, and the problems began almost immediately. Owners reported software faults, and the company struggled to fix them fast enough. In June twenty twenty-four, Fisker filed for bankruptcy. Around eleven thousand Ocean owners were left holding cars that had cost tens of thousands of dollars, with no dealer network, because Fisker sold directly, and with open safety recalls.

What happened next shows how different it is when a modern, connected car loses its maker. A bankruptcy judge ruled that the company would supply parts for two hardware recalls, but owners would pay for the labour. The company that bought the remaining stock, American Lease, also bought access to the software and cloud services the cars depend on. Owners formed their own association to keep their cars working, and later clashed with American Lease over who should pay for those services.

That is why Fisker is number one. When an older car loses its maker, you need parts and a good mechanic. When a software-defined car loses its maker, you may also need servers, code and updates that only the manufacturer could provide.""",
     [("ia", "electric suv"), ("stock", "electric car charging"), ("ia", "electric car"), ("ia", "car software screen"),
      ("stock", "electric car"), ("ia", "car dashboard screen"), ("ia", "server room"), ("ia", "electric car charging")],
     "electric car"),

    ("The Warning Signs Today", 4, """So what do all ten of these stories have in common? Look closely and the same warning signs appear before almost every collapse. First, a shrinking line-up, with models discontinued and no replacements ready. Second, a parent company in trouble, or a parent with too many brands chasing the same buyers. Third, a brand without a clear identity, selling cars that are barely different from cheaper cousins. And fourth, failed rescue deals, sales and mergers that fall apart at the last moment.

Are any brands showing some of these signs today? Two examples stand out, and to be clear, this is not a prediction that they will die. Jaguar stopped selling new cars while it prepares to relaunch as an all-electric luxury brand, with a four-door electric grand tourer expected to cost around one hundred and thirty thousand dollars and due to be revealed in October twenty twenty-six. That is a huge bet, made with almost no new cars in showrooms. And Nissan, after its planned merger with Honda collapsed in twenty twenty-five, launched a restructuring plan that cuts its number of factories from seventeen to ten. Nissan is a giant and still sells hundreds of thousands of cars, but these are exactly the kind of signals worth watching.

So how do you protect yourself? Before you buy, ask who stands behind the warranty and the parts, and whether the brand shares components with a larger, healthy company. Look at how many dealers near you can service the car. For electric and connected cars, ask what happens to the software and the app if the company fails. And remember the pattern from this list. The safest orphan cars were the ones built from shared parts, and the riskiest were the ones that depended entirely on a single, struggling company.

If this video gave you a new way to look at car brands, subscribe to the channel and help us reach our first one thousand subscribers. And tell me in the comments, which brand do you think is most at risk today? Thank you for watching.""",
     [("stock", "car dealership lot"), ("ia", "empty showroom"), ("ia", "jaguar car"), ("stock", "luxury car"),
      ("ia", "nissan car"), ("ia", "car factory"), ("ia", "car keys handshake"), ("stock", "car traffic"),
      ("ia", "car mechanic"), ("ia", "car parts"), ("ia", "electric car charging"), ("stock", "car dealership")],
     "car dealership"),
]

CAPITULOS = [
    "Hook, opening call to subscribe, and numbers ten to eight",
    "Numbers seven to five: GM's crisis and quiet exits",
    "Numbers four to two: national icons and orphaned owners",
    "Number one, the warning signs today and how to protect yourself",
]

DESCRICAO = """What really happens to the owners when a car brand dies? We count down ten brands that disappeared, from Scion and Mercury to Pontiac, Hummer, Holden, Saab and Fisker, and look at what each collapse meant for the people who still had the cars: warranties, parts, dealers, resale values and, in the newest case, software and cloud services.

At the end, we look at the warning signs that appeared before almost every collapse, the brands showing some of those signs today, and the questions to ask before you buy any new car.

Which brand do you think is most at risk today? Tell us in the comments, and subscribe to help the channel reach its first 1,000 subscribers."""

TAGS = ["car brands that died", "dead car brands", "car brands collapsing", "orphan cars", "Fisker bankruptcy",
        "Saab bankruptcy", "Pontiac", "Oldsmobile", "Hummer", "Holden", "Scion", "Mercury", "car buying advice",
        "car brands to avoid", "car industry news"]


def montar():
    cenas = []
    for secao, cap, texto, buscas, segura in SECOES:
        for i, trecho in enumerate(rot._dividir_em_cenas(texto)):
            # ("wiki", "Saab 900") busca a foto exata (modelo, animal, ponte, máquina...) no Wikimedia Commons;
            # se não achar, a cena usa a busca segura
            tipo, busca = buscas[i % len(buscas)]
            wiki = busca if tipo == "wiki" else ""
            busca = segura if wiki else busca
            cenas.append({"secao": secao, "capitulo": cap, "narracao": trecho, "visual": "ia" if wiki else tipo,
                          "busca_stock": busca, "busca_segura": segura, "busca_wiki": wiki,
                          "prompt_imagem": f"{wiki or busca}, photorealistic"})
    for n, cena in enumerate(cenas, 1):
        cena["id"] = n

    capitulos_texto = ["\n\n".join(t for _, c, t, _, _ in SECOES if c == n) for n in range(1, 5)]
    ficha = {
        "titulo_final": TITULO, "nicho": "C",
        "nicho_descricao": "Curiosidades / fatos - marcas de carro extintas e o destino dos donos",
        "registro": "Inglês formal, claro e didático, ritmo de narração",
        "promessa": "Mostrar dez marcas que morreram, o que aconteceu com quem tinha os carros e os sinais de alerta de hoje",
        "contexto": "Tema: fim de marcas de automóveis. Recorte: de 2004 (Oldsmobile) a 2024 (Fisker), com foco nos EUA, "
                    "mais Holden (Austrália) e Saab (Suécia)",
        "fatos_principais": FATOS, "personagens": [], "abertura": "cena reconstruída de um momento histórico",
        "referencia_acessivel": True,
        "observacao_referencia": "Vídeo e transcrição analisados. Usado só como molde de apelo; o ângulo (marcas que já "
                                 "morreram e o destino dos donos), a lista e o texto são novos.",
        "capitulos": [{"numero": n, "titulo_no_idioma": s, "resumo": s} for n, s in enumerate(CAPITULOS, 1)],
    }
    entrada = {"idioma": "inglês", "referencia": "https://www.youtube.com/watch?v=ooH2clmMSJ0", "nicho": "curiosidades",
               "capitulos": 4, "caracteres": 20000, "meta": "new channel, goal of 1,000 subscribers",
               "observacoes": "Roteiro escrito à mão com fatos verificados; CTA de inscrição também na abertura."}
    r = {
        "titulo": TITULO, "idioma": "inglês", "idioma_codigo": "en", "voz": "en-US-AndrewNeural", "nicho": "C",
        "entrada": entrada, "ficha": ficha, "capitulos_texto": capitulos_texto, "revisoes": [], "checklist": [],
        "descricao_youtube": DESCRICAO, "tags": TAGS, "criado_em": datetime.now().isoformat(timespec="seconds"),
        "cenas": cenas,
    }
    (PASTA / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    (PASTA / "roteiro.md").write_text(rot.roteiro_md(r), encoding="utf-8")
    (PASTA / "para_gravar.txt").write_text(rot.para_gravar(r), encoding="utf-8")
    (PASTA / "ficha.md").write_text(rot.ficha_md(ficha, entrada), encoding="utf-8")
    total = sum(len(t) for t in capitulos_texto)
    print(f"{len(cenas)} cenas, {total:,} caracteres (~{total / rot.CARACTERES_POR_MINUTO:.0f} min), "
          f"por capítulo: {[len(t) for t in capitulos_texto]}")
    digitos = [c["id"] for c in cenas if any(ch.isdigit() for ch in c["narracao"])]
    print("cenas com dígitos:", digitos or "nenhuma")
    rot._registrar_abertura(ficha["abertura"])


if __name__ == "__main__":
    montar()
