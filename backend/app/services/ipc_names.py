"""Human names for IPC/CPC subclasses."""

SUBCLASS_NAMES: dict[str, str] = {
    "H01M": "Batteries & fuel cells",
    "H01G": "Capacitors & supercapacitors",
    "H02J": "Power supply & distribution circuits",
    "H02S": "Photovoltaic power generation",
    "H02K": "Electric machines & generators",
    "H02M": "Power conversion",
    "H02P": "Electric motor control",
    "H01B": "Cables & conductors",
    "H01R": "Electrical connectors",
    "H05B": "Electric heating",
    "F03D": "Wind turbines",
    "F03G": "Mechanical power production",
    "F24S": "Solar heat collectors",
    "F28D": "Heat exchange & thermal storage",
    "F01K": "Steam power plant",
    "F02C": "Gas turbine plant",
    "G21B": "Fusion reactors",
    "G21C": "Nuclear reactors",
    "Y02E": "Low-carbon energy technology",
    "Y04S": "Smart grid technology",
    "Y02T": "Low-carbon transport",
    "Y02P": "Low-carbon manufacturing",

    "C01B": "Non-metallic elements & compounds",
    "C01G": "Metal compounds",
    "C04B": "Ceramics, cement & concrete",
    "C08G": "Polymer chemistry",
    "C08J": "Polymer processing",
    "C08L": "Polymer compositions",
    "C09D": "Coatings & inks",
    "C22C": "Alloys",
    "C23C": "Surface coating",
    "C25B": "Electrolytic processes",
    "C25D": "Electroplating",
    "B01D": "Separation processes",
    "B01J": "Catalysts & chemical processes",
    "B82Y": "Nanotechnology",
    "B32B": "Layered products",

    "G06F": "Digital data processing",
    "G06N": "Machine learning & AI models",
    "G06Q": "Business & administrative data processing",
    "G06T": "Image data processing",
    "G06V": "Image & video recognition",
    "G16C": "Computational chemistry",
    "G16H": "Health informatics",
    "G11C": "Memory & storage devices",
    "G05B": "Control systems",
    "G05D": "Non-electric variable control",
    "G01N": "Materials analysis & testing",
    "G01R": "Electrical measurement",
    "G02B": "Optical elements",
    "G02F": "Optical modulation",
    "H03K": "Pulse & switching circuits",
    "H03M": "Coding & conversion",

    "H04L": "Digital transmission & network security",
    "H04W": "Wireless networks",
    "H04N": "Image & video communication",
    "H04B": "Transmission systems",
    "H04Q": "Switching & selecting",

    "H01L": "Semiconductor devices",
    "H10N": "Semiconductor devices (specialised)",
    "H05K": "Printed circuits & assemblies",

    "B25J": "Manipulators & robots",
    "B60L": "Electric vehicle propulsion",
    "B60W": "Vehicle control systems",
    "B62D": "Vehicle construction",
    "B64C": "Aeroplanes & aircraft",
    "B64U": "Unmanned aerial vehicles",
    "G08G": "Traffic control systems",
    "F16H": "Gearing & transmissions",

    "A61B": "Diagnosis & surgery",
    "A61K": "Medicinal preparations",
    "A61M": "Devices for introducing media into the body",
    "A61N": "Electrotherapy & radiation therapy",
    "C07D": "Heterocyclic compounds",
    "C07K": "Peptides",
    "C12N": "Genetic engineering & microorganisms",
    "C12Q": "Nucleic acid & enzyme assays",
    "C40B": "Combinatorial chemistry",
    "G01S": "Radio & acoustic detection",
}


def name_for(code: str | None) -> str | None:
    """Human name for a subclass, or None when unmapped."""
    if not code:
        return None
    return SUBCLASS_NAMES.get(code.strip().upper()[:4])


def describe(code: str | None) -> str | None:
    """Label including the code, e.g."""
    label = name_for(code)
    if not label:
        return None
    return f"{label} ({code.strip().upper()[:4]})"
