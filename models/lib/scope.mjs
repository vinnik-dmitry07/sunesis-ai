// The Python port of the Ginzu (models/dcf.py) models only the branches every case here uses.
// This guard reads the effective values in the page engine and names any active feature the port does not model,
// so an export refuses instead of producing a workbook that silently disagrees with the page.
export function unsupportedFeatures(engine) {
  const v = id => engine.safe(id).value;
  const yes = id => String(v(id) ?? '').toUpperCase() === 'YES';
  const out = [];
  if (yes('Input sheet!B61') || Math.abs(v('Valuation output!B10') ?? 0) > 0) out.push('net operating loss carryforward (Input sheet!B61)');
  if (yes('Input sheet!B51') || Math.abs(v('Valuation output!B22') ?? 0) > 0) out.push('distress adjustment, probability of failure (Input sheet!B51)');
  if (yes('Input sheet!B37') || Math.abs(v('Valuation output!B30') ?? 0) > 0) out.push('employee options valued by the option sheet (Input sheet!B37)');
  if (yes('Input sheet!B70')) out.push('trapped cash haircut (Input sheet!B70)');
  const lag = yes('Input sheet!B56') ? v('Input sheet!B57') : 1;
  if (lag !== 1) out.push(`reinvestment lag of ${lag} years instead of 1 (Input sheet!B56, B57)`);
  return out;
}
