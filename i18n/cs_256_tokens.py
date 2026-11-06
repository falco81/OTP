# 1.0.256 (tokens): the owner inside an exported .totp file; no switch back to small letters over
# tokens named with capitals.
S256_TOKENS = {
 'no owner written inside (an otp export before 1.0.256, or a folder zipped): the owner is read from the file name only':
  'uvnitř není zapsaný vlastník (export otp starší než 1.0.256, nebo zabalená složka): vlastník se čte jen z názvu souboru',
}
P256_TOKENS = {
 'not imported: the file is named for {0}, but the token in it is of {1}':
  'neimportováno: soubor je pojmenovaný pro {0}, ale token v něm patří {1}',
 'the file is named for {0}, but the token in it is of {1}':
  'soubor je pojmenovaný pro {0}, ale token v něm patří {1}',
 '{0} token(s) have capital letters in their names ({1}): in small letters they would be found by nobody - rename them to small letters first (the token\'s window - Move to), then switch to small letters':
  'tokeny s velkými písmeny ve jménu: {0} ({1}) – v malých písmenech by je nikdo nenašel; nejdřív je přejmenujte na malá písmena (okno tokenu → Přesunout na), pak přepněte na malá písmena',
 '{0} token(s) have capital letters in their names ({1}): in small letters they would be found by nobody - rename them to small letters first (the token\'s window - Move to), then switch to small letters (nothing saved)':
  'tokeny s velkými písmeny ve jménu: {0} ({1}) – v malých písmenech by je nikdo nenašel; nejdřív je přejmenujte na malá písmena (okno tokenu → Přesunout na), pak přepněte na malá písmena (nic nebylo uloženo)',
 '{0} token(s) have capital letters in their names ({1}): in small letters they would be found by nobody - rename them to small letters first (the token\'s window - Move to), then switch to small letters - nothing was imported':
  'tokeny s velkými písmeny ve jménu: {0} ({1}) – v malých písmenech by je nikdo nenašel; nejdřív je přejmenujte na malá písmena (okno tokenu → Přesunout na), pak přepněte na malá písmena – nic nebylo importováno',
}
