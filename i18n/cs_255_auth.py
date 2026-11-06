# 1.0.255 (auth): the administration's second step under the guard, the one-time code's SMS
# attributes, the enrolment pages' lockouts.
S255_AUTH = {
 # LOCKOUT_KINDS (90_api)
 'the one-time code before the first token (enrolment pages)':
  'jednorázový kód před prvním tokenem (stránky registrace)',
 'signing in by the load balancer, per name (enrolment pages)':
  'přihlášení přes load balancer, podle jména (stránky registrace)',
 'signing in by the load balancer, per address (enrolment pages)':
  'přihlášení přes load balancer, podle adresy (stránky registrace)',
 # Settings (00_head): NAMES, SAYS
 'Its SMS only to a number in these attributes':
  'Jeho SMS jen na číslo v těchto atributech',
 "The attributes of the directory the one-time code by SMS may go to - one to four names, such as extensionAttribute5 or employeeMobile: the first with a number is taken, read from the person's entry at the sign-in. Empty: the mobile number as the directory's card reads it (mobile, then telephoneNumber, unless changed there) - as until now. In Active Directory everybody may change mobile and telephoneNumber of their own account (Personal Information): somebody who found out a password could put their own number there first, and the code went to them. Name an attribute only the administrators write. The e-mail address is not affected.":
  'Atributy adresáře, na jejichž číslo smí jít jednorázový kód přes SMS – jeden až čtyři názvy, například extensionAttribute5 nebo employeeMobile: bere se první, který číslo má, čte se z vlastního záznamu dotyčného při přihlášení. Prázdné: mobilní číslo tak, jak ho čte karta adresáře (mobile, pak telephoneNumber, pokud tam není změněno) – jako dosud. V Active Directory si každý může u svého účtu změnit mobile i telephoneNumber (Osobní údaje): kdo zjistil heslo, mohl tam nejdřív dát své číslo a kód přišel jemu. Uveďte atribut, který zapisují jen správci. E-mailové adresy se to netýká.',
 'portal_first_sms_attr: four attributes at most':
  'portal_first_sms_attr: nejvýše čtyři atributy',
}
P255_AUTH = {
 # The second step held under the guard (90m_mfa: MFA_BLOCKED_WORDS)
 'the second step of this account in the database was not written by otp - nothing can be set up over it: another full administrator resets it (Accounts), or root with  otp --reset-2fa {0}':
  'druhý krok tohoto účtu v databázi nezapsal otp – přes něj nelze nastavit nic jiného: resetuje ho jiný plný správce (Účty), nebo root příkazem  otp --reset-2fa {0}',
 # The Settings page's warning (90_api: portal_first_sms_warning)
 'The one-time code by SMS goes to {0} - in Active Directory everybody may change these on their own account, so a password found out is enough to put another number there first. Name an attribute only the administrators write in "Its SMS only to a number in these attributes".':
  'Jednorázový kód přes SMS jde na {0} – v Active Directory si je každý může změnit u svého účtu, takže stačí zjištěné heslo a lze tam nejdřív dát jiné číslo. V nastavení „Jeho SMS jen na číslo v těchto atributech“ uveďte atribut, který zapisují jen správci.',
 'portal_first_sms_attr: {0} is not the name of an attribute':
  'portal_first_sms_attr: {0} není název atributu',
}
