# 1.0.183: a key and then the code; the language of an SSH token's mails and SMS; the gate's port.
S212 = {
 "otp’s gate for SSH": "Brána otp pro SSH",
 "otp’s gate for SSH: the port tried first": "Brána otp pro SSH: port zkoušený jako první",
 "pam_radius of each node asks otp on 127.0.0.1 at this port, never from the network - nothing to open in the firewall. Where something else has it, each node takes the next free one of 18129-18199 by itself and tells its pam_radius; each node’s card above says which.":
  "pam_radius každého uzlu se ptá otp na 127.0.0.1 na tomto portu, nikdy ze sítě – ve firewallu se nic neotevírá. Kde ho má obsazený něco jiného, každý uzel si sám vezme další volný z 18129–18199 a řekne ho svému pam_radius; který to je, ukazuje karta každého uzlu výše.",
 "A key, and then the code": "Klíč, a pak kód",
 "On: an SSH key alone no longer lets in - after the key sshd asks for the code too (AuthenticationMethods publickey,keyboard-interactive), for the accounts the code is asked of. Off: a key alone lets in, the code is asked only where a password would be.":
  "Zapnuto: samotný SSH klíč už nepustí dovnitř – po klíči sshd chce i kód (AuthenticationMethods publickey,keyboard-interactive), u účtů, po kterých se kód chce. Vypnuto: samotný klíč pustí dovnitř, kód se chce jen tam, kde by se chtělo heslo.",
 "A key and then the code - as set below.": "Klíč a pak kód – jak je nastavené níže.",
 "A key alone still lets in - sshd asks for the code only where it asks for a password. For a key and the code: below.":
  "Samotný klíč dál pustí dovnitř – sshd chce kód jen tam, kde by chtěl heslo. Pro klíč a k tomu kód: níže.",
 "A key and then the code: whoever the code is asked of needs an SSH key of their own in ~/.ssh/authorized_keys on every node - without one, nobody gets in that way.":
  "Klíč a pak kód: kdo má zadávat kód, potřebuje vlastní SSH klíč v ~/.ssh/authorized_keys na každém uzlu – bez něj se takhle nedostane nikdo.",
 "The language of its mails and SMS": "Jazyk jeho e-mailů a SMS",
 "The words as Settings → Message texts has them, SSH, in this language.": "Texty podle Nastavení → Texty zpráv, SSH, v tomto jazyce.",
 "Czech": "čeština", "English": "angličtina",
}
P212 = {
 "A key and then the code: whoever the code is asked of needs an SSH key of their own in ~/.ssh/authorized_keys on every node - without one, nobody gets in that way. Root has no key on {0}.":
  "Klíč a pak kód: kdo má zadávat kód, potřebuje vlastní SSH klíč v ~/.ssh/authorized_keys na každém uzlu – bez něj se takhle nedostane nikdo. Root nemá klíč na {0}.",
}
