/**
 * Science helpers for the Workbench's Tools and Labs: a safe calculator (no eval),
 * unit conversion, physical constants, the periodic table and chemistry formulas.
 */

// ---- Calculator: numbers, + - * / ^ %, parentheses, functions and constants. Never eval().
const FUNCS: Record<string, (x: number) => number> = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
  sinh: Math.sinh, cosh: Math.cosh, tanh: Math.tanh, sqrt: Math.sqrt, cbrt: Math.cbrt, abs: Math.abs,
  ln: Math.log, log: Math.log10, log2: Math.log2, exp: Math.exp, floor: Math.floor, ceil: Math.ceil, round: Math.round,
  deg: (x: number) => (x * 180) / Math.PI, rad: (x: number) => (x * Math.PI) / 180,
};
const CONSTS: Record<string, number> = { pi: Math.PI, e: Math.E, tau: 2 * Math.PI, phi: (1 + Math.sqrt(5)) / 2 };

export function calculate(input: string, degrees = false): number {
  const text = input.replace(/\s+/g, "").replace(/×/g, "*").replace(/÷/g, "/").replace(/π/g, "pi");
  let at = 0;
  const peek = () => text[at];
  const fail = (): never => { throw new Error(at < text.length ? `Didn't understand “${text.slice(at, at + 8)}”` : "The expression ended early."); };
  const trig = new Set(["sin", "cos", "tan"]);
  const atrig = new Set(["asin", "acos", "atan"]);
  function primary(): number {
    if (peek() === "(") { at++; const value = sum(); if (peek() !== ")") fail(); at++; return value; }
    if (peek() === "-") { at++; return -power(); }
    if (peek() === "+") { at++; return power(); }
    const num = /^(\d+\.?\d*|\.\d+)(e[+-]?\d+)?/i.exec(text.slice(at));
    if (num) { at += num[0].length; return Number(num[0]); }
    const name = /^[a-z][a-z0-9]*/i.exec(text.slice(at));
    if (name) {
      const word = name[0].toLowerCase();
      at += name[0].length;
      if (word in FUNCS) {
        if (peek() !== "(") fail();
        at++; let arg = sum(); if (peek() !== ")") fail(); at++;
        if (degrees && trig.has(word)) arg = (arg * Math.PI) / 180;
        const out = FUNCS[word](arg);
        return degrees && atrig.has(word) ? (out * 180) / Math.PI : out;
      }
      if (word in CONSTS) return CONSTS[word];
      at -= name[0].length;
    }
    return fail();
  }
  function postfix(): number {
    let value = primary();
    while (peek() === "!") { at++; if (value < 0 || value > 170 || !Number.isInteger(value)) throw new Error("Factorial needs a whole number 0–170."); let f = 1; for (let i = 2; i <= value; i++) f *= i; value = f; }
    return value;
  }
  function power(): number {
    const base = postfix();
    if (peek() === "^") { at++; return base ** power(); }
    return base;
  }
  function product(): number {
    let value = power();
    for (;;) {
      if (peek() === "*") { at++; value *= power(); }
      else if (peek() === "/") { at++; value /= power(); }
      else if (peek() === "%") { at++; value %= power(); }
      else if (peek() === "(" || (peek() && /[a-z]/i.test(peek()))) value *= power();  // 2pi, 3(4+1)
      else return value;
    }
  }
  function sum(): number {
    let value = product();
    for (;;) {
      if (peek() === "+") { at++; value += product(); }
      else if (peek() === "-") { at++; value -= product(); }
      else return value;
    }
  }
  if (!text) throw new Error("Type an expression.");
  const result = sum();
  if (at !== text.length) fail();
  return result;
}

// ---- Units: each category maps unit -> factor to a base unit (temperature is special).
export const UNITS: Record<string, Record<string, number>> = {
  Length: { m: 1, km: 1e3, cm: 1e-2, mm: 1e-3, µm: 1e-6, nm: 1e-9, in: 0.0254, ft: 0.3048, yd: 0.9144, mi: 1609.344, "nautical mi": 1852, ly: 9.4607e15, au: 1.495978707e11 },
  Mass: { kg: 1, g: 1e-3, mg: 1e-6, t: 1e3, lb: 0.45359237, oz: 0.028349523125, st: 6.35029318, "u (Da)": 1.66053906660e-27 },
  Volume: { L: 1, mL: 1e-3, "m³": 1e3, "cm³": 1e-3, "gal (US)": 3.785411784, "qt (US)": 0.946352946, "cup (US)": 0.2365882365, "fl oz (US)": 0.0295735296, "gal (UK)": 4.54609 },
  Area: { "m²": 1, "km²": 1e6, "cm²": 1e-4, ha: 1e4, acre: 4046.8564224, "ft²": 0.09290304, "in²": 0.00064516, "mi²": 2589988.110336 },
  Speed: { "m/s": 1, "km/h": 1 / 3.6, mph: 0.44704, knot: 0.514444, "ft/s": 0.3048, mach: 343, c: 299792458 },
  Pressure: { Pa: 1, kPa: 1e3, MPa: 1e6, bar: 1e5, atm: 101325, psi: 6894.757293, mmHg: 133.322387, torr: 133.322368 },
  Energy: { J: 1, kJ: 1e3, MJ: 1e6, cal: 4.184, kcal: 4184, Wh: 3600, kWh: 3.6e6, eV: 1.602176634e-19, BTU: 1055.05585 },
  Power: { W: 1, kW: 1e3, MW: 1e6, hp: 745.699872, "BTU/h": 0.29307107 },
  Data: { B: 1, KB: 1e3, MB: 1e6, GB: 1e9, TB: 1e12, KiB: 1024, MiB: 1048576, GiB: 1073741824, TiB: 1099511627776, bit: 0.125 },
  Time: { s: 1, ms: 1e-3, µs: 1e-6, min: 60, h: 3600, day: 86400, week: 604800, year: 31557600 },
  Angle: { rad: 1, deg: Math.PI / 180, grad: Math.PI / 200, turn: 2 * Math.PI, arcmin: Math.PI / 10800, arcsec: Math.PI / 648000 },
  Frequency: { Hz: 1, kHz: 1e3, MHz: 1e6, GHz: 1e9, rpm: 1 / 60 },
  Temperature: { "°C": 1, "°F": 1, K: 1 },
};

export function convert(value: number, category: string, from: string, to: string): number {
  if (category === "Temperature") {
    const kelvin = from === "°C" ? value + 273.15 : from === "°F" ? (value - 32) * 5 / 9 + 273.15 : value;
    return to === "°C" ? kelvin - 273.15 : to === "°F" ? (kelvin - 273.15) * 9 / 5 + 32 : kelvin;
  }
  const table = UNITS[category];
  return (value * table[from]) / table[to];
}

// ---- Physical constants (CODATA 2018 exact/recommended values).
export const CONSTANTS: { symbol: string; name: string; value: number; unit: string }[] = [
  { symbol: "c", name: "Speed of light", value: 299792458, unit: "m/s" },
  { symbol: "G", name: "Gravitational constant", value: 6.6743e-11, unit: "m³/(kg·s²)" },
  { symbol: "h", name: "Planck constant", value: 6.62607015e-34, unit: "J·s" },
  { symbol: "ħ", name: "Reduced Planck constant", value: 1.054571817e-34, unit: "J·s" },
  { symbol: "e", name: "Elementary charge", value: 1.602176634e-19, unit: "C" },
  { symbol: "k_B", name: "Boltzmann constant", value: 1.380649e-23, unit: "J/K" },
  { symbol: "N_A", name: "Avogadro constant", value: 6.02214076e23, unit: "1/mol" },
  { symbol: "R", name: "Gas constant", value: 8.314462618, unit: "J/(mol·K)" },
  { symbol: "m_e", name: "Electron mass", value: 9.1093837015e-31, unit: "kg" },
  { symbol: "m_p", name: "Proton mass", value: 1.67262192369e-27, unit: "kg" },
  { symbol: "m_n", name: "Neutron mass", value: 1.67492749804e-27, unit: "kg" },
  { symbol: "ε₀", name: "Vacuum permittivity", value: 8.8541878128e-12, unit: "F/m" },
  { symbol: "μ₀", name: "Vacuum permeability", value: 1.25663706212e-6, unit: "N/A²" },
  { symbol: "σ", name: "Stefan–Boltzmann constant", value: 5.670374419e-8, unit: "W/(m²·K⁴)" },
  { symbol: "F", name: "Faraday constant", value: 96485.33212, unit: "C/mol" },
  { symbol: "a₀", name: "Bohr radius", value: 5.29177210903e-11, unit: "m" },
  { symbol: "α", name: "Fine-structure constant", value: 7.2973525693e-3, unit: "" },
  { symbol: "g", name: "Standard gravity", value: 9.80665, unit: "m/s²" },
  { symbol: "atm", name: "Standard atmosphere", value: 101325, unit: "Pa" },
];

// ---- Periodic table: [number, symbol, name, standard atomic weight, category].
const RAW = "1 H Hydrogen 1.008 nonmetal|2 He Helium 4.0026 noble|3 Li Lithium 6.94 alkali|4 Be Beryllium 9.0122 alkaline|5 B Boron 10.81 metalloid|6 C Carbon 12.011 nonmetal|7 N Nitrogen 14.007 nonmetal|8 O Oxygen 15.999 nonmetal|9 F Fluorine 18.998 halogen|10 Ne Neon 20.180 noble|11 Na Sodium 22.990 alkali|12 Mg Magnesium 24.305 alkaline|13 Al Aluminium 26.982 post-transition|14 Si Silicon 28.085 metalloid|15 P Phosphorus 30.974 nonmetal|16 S Sulfur 32.06 nonmetal|17 Cl Chlorine 35.45 halogen|18 Ar Argon 39.95 noble|19 K Potassium 39.098 alkali|20 Ca Calcium 40.078 alkaline|21 Sc Scandium 44.956 transition|22 Ti Titanium 47.867 transition|23 V Vanadium 50.942 transition|24 Cr Chromium 51.996 transition|25 Mn Manganese 54.938 transition|26 Fe Iron 55.845 transition|27 Co Cobalt 58.933 transition|28 Ni Nickel 58.693 transition|29 Cu Copper 63.546 transition|30 Zn Zinc 65.38 transition|31 Ga Gallium 69.723 post-transition|32 Ge Germanium 72.630 metalloid|33 As Arsenic 74.922 metalloid|34 Se Selenium 78.971 nonmetal|35 Br Bromine 79.904 halogen|36 Kr Krypton 83.798 noble|37 Rb Rubidium 85.468 alkali|38 Sr Strontium 87.62 alkaline|39 Y Yttrium 88.906 transition|40 Zr Zirconium 91.224 transition|41 Nb Niobium 92.906 transition|42 Mo Molybdenum 95.95 transition|43 Tc Technetium 98 transition|44 Ru Ruthenium 101.07 transition|45 Rh Rhodium 102.91 transition|46 Pd Palladium 106.42 transition|47 Ag Silver 107.87 transition|48 Cd Cadmium 112.41 transition|49 In Indium 114.82 post-transition|50 Sn Tin 118.71 post-transition|51 Sb Antimony 121.76 metalloid|52 Te Tellurium 127.60 metalloid|53 I Iodine 126.90 halogen|54 Xe Xenon 131.29 noble|55 Cs Caesium 132.91 alkali|56 Ba Barium 137.33 alkaline|57 La Lanthanum 138.91 lanthanide|58 Ce Cerium 140.12 lanthanide|59 Pr Praseodymium 140.91 lanthanide|60 Nd Neodymium 144.24 lanthanide|61 Pm Promethium 145 lanthanide|62 Sm Samarium 150.36 lanthanide|63 Eu Europium 151.96 lanthanide|64 Gd Gadolinium 157.25 lanthanide|65 Tb Terbium 158.93 lanthanide|66 Dy Dysprosium 162.50 lanthanide|67 Ho Holmium 164.93 lanthanide|68 Er Erbium 167.26 lanthanide|69 Tm Thulium 168.93 lanthanide|70 Yb Ytterbium 173.05 lanthanide|71 Lu Lutetium 174.97 lanthanide|72 Hf Hafnium 178.49 transition|73 Ta Tantalum 180.95 transition|74 W Tungsten 183.84 transition|75 Re Rhenium 186.21 transition|76 Os Osmium 190.23 transition|77 Ir Iridium 192.22 transition|78 Pt Platinum 195.08 transition|79 Au Gold 196.97 transition|80 Hg Mercury 200.59 transition|81 Tl Thallium 204.38 post-transition|82 Pb Lead 207.2 post-transition|83 Bi Bismuth 208.98 post-transition|84 Po Polonium 209 post-transition|85 At Astatine 210 halogen|86 Rn Radon 222 noble|87 Fr Francium 223 alkali|88 Ra Radium 226 alkaline|89 Ac Actinium 227 actinide|90 Th Thorium 232.04 actinide|91 Pa Protactinium 231.04 actinide|92 U Uranium 238.03 actinide|93 Np Neptunium 237 actinide|94 Pu Plutonium 244 actinide|95 Am Americium 243 actinide|96 Cm Curium 247 actinide|97 Bk Berkelium 247 actinide|98 Cf Californium 251 actinide|99 Es Einsteinium 252 actinide|100 Fm Fermium 257 actinide|101 Md Mendelevium 258 actinide|102 No Nobelium 259 actinide|103 Lr Lawrencium 266 actinide|104 Rf Rutherfordium 267 transition|105 Db Dubnium 268 transition|106 Sg Seaborgium 269 transition|107 Bh Bohrium 270 transition|108 Hs Hassium 277 transition|109 Mt Meitnerium 278 unknown|110 Ds Darmstadtium 281 unknown|111 Rg Roentgenium 282 unknown|112 Cn Copernicium 285 transition|113 Nh Nihonium 286 unknown|114 Fl Flerovium 289 unknown|115 Mc Moscovium 290 unknown|116 Lv Livermorium 293 unknown|117 Ts Tennessine 294 unknown|118 Og Oganesson 294 unknown";
export type Element = { number: number; symbol: string; name: string; mass: number; category: string };
export const ELEMENTS: Element[] = RAW.split("|").map(row => {
  const [number, symbol, name, mass, category] = row.split(" ");
  return { number: Number(number), symbol, name, mass: Number(mass), category };
});
const BY_SYMBOL = new Map(ELEMENTS.map(element => [element.symbol, element]));

/** Molar mass of a formula like H2SO4, Ca(OH)2, CuSO4·5H2O. Returns g/mol and each element's count. */
export function molarMass(formula: string): { mass: number; parts: { symbol: string; count: number; mass: number }[] } {
  const counts = new Map<string, number>();
  const groups = formula.replace(/\s+/g, "").split(/[·.*]/);
  for (const group of groups) {
    const lead = /^(\d+)/.exec(group);
    const factor = lead ? Number(lead[1]) : 1;
    let text = lead ? group.slice(lead[0].length) : group;
    let at = 0;
    const read = (): Map<string, number> => {
      const local = new Map<string, number>();
      while (at < text.length) {
        const ch = text[at];
        if (ch === "(" || ch === "[") {
          at++; const inner = read();
          if (text[at] !== ")" && text[at] !== "]") throw new Error("A bracket isn't closed.");
          at++;
          const num = /^\d+/.exec(text.slice(at)); const n = num ? Number(num[0]) : 1; if (num) at += num[0].length;
          inner.forEach((value, key) => local.set(key, (local.get(key) ?? 0) + value * n));
        } else if (ch === ")" || ch === "]") {
          return local;
        } else {
          const match = /^([A-Z][a-z]?)(\d*)/.exec(text.slice(at));
          if (!match || !BY_SYMBOL.has(match[1])) throw new Error(`Unknown element near “${text.slice(at, at + 3)}”.`);
          at += match[0].length;
          local.set(match[1], (local.get(match[1]) ?? 0) + (match[2] ? Number(match[2]) : 1));
        }
      }
      return local;
    };
    const found = read();
    if (at !== text.length) throw new Error("Couldn't read the whole formula.");
    found.forEach((value, key) => counts.set(key, (counts.get(key) ?? 0) + value * factor));
    text = "";
  }
  if (!counts.size) throw new Error("Type a formula, e.g. H2SO4.");
  const parts = [...counts].map(([symbol, count]) => ({ symbol, count, mass: count * BY_SYMBOL.get(symbol)!.mass }));
  return { mass: parts.reduce((sum, part) => sum + part.mass, 0), parts };
}

export const formatNumber = (value: number, digits = 6) =>
  !Number.isFinite(value) ? String(value) : Math.abs(value) !== 0 && (Math.abs(value) >= 1e9 || Math.abs(value) < 1e-4)
    ? value.toExponential(digits - 1) : Number(value.toPrecision(digits)).toString();
