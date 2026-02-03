def calculer_facture_france(prix_ht, tva):
    # Une logique un peu longue pour déclencher la signature
    temp = prix_ht * tva
    total = prix_ht + temp
    if total > 100:
        print("Gros montant")
    return round(total, 2)

def process_order_us(amount, tax_rate):
    # La structure est IDENTIQUE, seuls les noms changent
    var_a = amount * tax_rate
    var_b = amount + var_a
    if var_b > 100:
        print("Gros montant")
    return round(var_b, 2)