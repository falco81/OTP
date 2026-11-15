/* ---- A certificate request made in this browser (1.0.283) ---------------------------------------------
   The key pair is made by the browser (WebCrypto) and never leaves it: the request (PKCS#10, DER written
   here) and the private key (PKCS#8 - encrypted with a passphrase by PBES2: PBKDF2-SHA-256 and AES-256-CBC,
   as openssl and Windows read it) are handed over as files. Nothing of it is sent to the server. */
var CSR_OID = {
  cn: '2.5.4.3', o: '2.5.4.10', ou: '2.5.4.11', l: '2.5.4.7', st: '2.5.4.8', c: '2.5.4.6',
  san: '2.5.29.17', eku: '2.5.29.37', ku: '2.5.29.15', bc: '2.5.29.19', extReq: '1.2.840.113549.1.9.14',
  upn: '1.3.6.1.4.1.311.20.2.3', template: '1.3.6.1.4.1.311.20.2', sidExt: '1.3.6.1.4.1.311.25.2',
  clientAuth: '1.3.6.1.5.5.7.3.2', smartcard: '1.3.6.1.4.1.311.20.2.2', email: '1.3.6.1.5.5.7.3.4',
  rsaSha256: '1.2.840.113549.1.1.11', ecdsaSha256: '1.2.840.10045.4.3.2', ecdsaSha384: '1.2.840.10045.4.3.3',
  pbes2: '1.2.840.113549.1.5.13', pbkdf2: '1.2.840.113549.1.5.12', hmacSha256: '1.2.840.113549.2.9',
  aes256cbc: '2.16.840.1.101.3.4.1.42'
};
function derLen(n) {
  if (n < 128) return [n];
  var b = [];
  while (n > 0) { b.unshift(n & 255); n = Math.floor(n / 256); }
  return [0x80 | b.length].concat(b);
}
function der(tag, body) {
  var b = body instanceof Uint8Array ? Array.prototype.slice.call(body) : body;
  return [tag].concat(derLen(b.length), b);
}
function derCat() {
  var out = [];
  for (var i = 0; i < arguments.length; i++) out = out.concat(arguments[i]);
  return out;
}
function derSeq() { return der(0x30, derCat.apply(null, arguments)); }
function derSet() { return der(0x31, derCat.apply(null, arguments)); }
function derOid(s) {
  var p = s.split('.').map(Number), out = [40 * p[0] + p[1]];
  for (var i = 2; i < p.length; i++) {
    var v = p[i], b = [v & 127];
    v = Math.floor(v / 128);
    while (v > 0) { b.unshift(0x80 | (v & 127)); v = Math.floor(v / 128); }
    out = out.concat(b);
  }
  return der(0x06, out);
}
function derUtf8(s) { return der(0x0c, Array.prototype.slice.call(new TextEncoder().encode(s))); }
function derAscii(tag, s) { var b = []; for (var i = 0; i < s.length; i++) b.push(s.charCodeAt(i) & 127); return der(tag, b); }
function derBmp(s) { var b = []; for (var i = 0; i < s.length; i++) { var c = s.charCodeAt(i); b.push(c >> 8, c & 255); } return der(0x1e, b); }
function derInt(bytes) {
  var b = Array.prototype.slice.call(bytes);
  while (b.length > 1 && b[0] === 0 && b[1] < 128) b.shift();
  if (b[0] >= 128) b.unshift(0);
  return der(0x02, b);
}
function derIntNum(n) { var b = []; do { b.unshift(n & 255); n = Math.floor(n / 256); } while (n > 0); return derInt(b); }
function derBits(bytes, unused) { return der(0x03, [unused || 0].concat(Array.prototype.slice.call(bytes))); }
function derOctets(bytes) { return der(0x04, Array.prototype.slice.call(bytes)); }
function derB64(bytes) {
  var s = '', a = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (var i = 0; i < a.length; i += 0x8000) s += String.fromCharCode.apply(null, a.subarray(i, i + 0x8000));
  return btoa(s);
}
function derPem(label, bytes) {
  return '-----BEGIN ' + label + '-----\n' + derB64(bytes).replace(/(.{64})/g, '$1\n').replace(/\n$/, '') + '\n-----END ' + label + '-----\n';
}
/* {key: 'rsa2048'|'rsa3072'|'rsa4096'|'p256'|'p384', subject: [[field, value]...] (cn, o, ou, l, st, c),
    upn, url, email (each '' when left out), eku: [oids], template, pass} -> {csr, key} (PEM) */
function csrMake(o) {
  var ec = /^p/.test(o.key), C = window.crypto.subtle;
  var alg = ec ? {name: 'ECDSA', namedCurve: o.key === 'p384' ? 'P-384' : 'P-256'}
    : {name: 'RSASSA-PKCS1-v1_5', modulusLength: parseInt(o.key.slice(3), 10), publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256'};
  var pair;
  return C.generateKey(alg, true, ['sign', 'verify']).then(function (p) {
    pair = p;
    return C.exportKey('spki', p.publicKey);
  }).then(function (spki) {
    var rdns = [];
    ['c', 'st', 'l', 'o', 'ou', 'cn'].forEach(function (f) {
      (o.subject || []).filter(function (x) { return x[0] === f && x[1]; }).forEach(function (x) {
        rdns.push(derSet(derSeq(derOid(CSR_OID[f]), f === 'c' ? derAscii(0x13, x[1].toUpperCase()) : derUtf8(x[1]))));
      });
    });
    var name = der(0x30, derCat.apply(null, rdns));
    var gn = [];
    if (o.upn) gn.push(der(0xa0, derCat(derOid(CSR_OID.upn), der(0xa0, derUtf8(o.upn)))));
    if (o.url) gn.push(derAscii(0x86, o.url));
    if (o.email) gn.push(derAscii(0x81, o.email));
    var exts = [];
    if (gn.length) exts.push(derSeq(derOid(CSR_OID.san), derOctets(der(0x30, derCat.apply(null, gn)))));
    if ((o.eku || []).length) exts.push(derSeq(derOid(CSR_OID.eku), derOctets(der(0x30, derCat.apply(null, o.eku.map(derOid))))));
    /* digitalSignature (+ keyEncipherment for RSA), critical */
    exts.push(derSeq(derOid(CSR_OID.ku), der(0x01, [0xff]), derOctets(derBits(ec ? [0x80] : [0xa0], 5))));
    if (o.template) exts.push(derSeq(derOid(CSR_OID.template), derOctets(derBmp(o.template))));
    var attrs = der(0xa0, derSeq(derOid(CSR_OID.extReq), derSet(der(0x30, derCat.apply(null, exts)))));
    var info = derSeq(derIntNum(0), name, Array.prototype.slice.call(new Uint8Array(spki)), attrs);
    var salg = ec ? {name: 'ECDSA', hash: o.key === 'p384' ? 'SHA-384' : 'SHA-256'} : {name: 'RSASSA-PKCS1-v1_5'};
    return C.sign(salg, pair.privateKey, new Uint8Array(info)).then(function (sig) {
      var s = new Uint8Array(sig), sigDer, aid;
      if (ec) {
        var h = s.length / 2;
        sigDer = derSeq(derInt(s.subarray(0, h)), derInt(s.subarray(h)));
        aid = derSeq(derOid(o.key === 'p384' ? CSR_OID.ecdsaSha384 : CSR_OID.ecdsaSha256));
      } else {
        sigDer = Array.prototype.slice.call(s);
        aid = derSeq(derOid(CSR_OID.rsaSha256), [0x05, 0x00]);
      }
      return derPem('CERTIFICATE REQUEST', new Uint8Array(derSeq(info, aid, derBits(sigDer, 0))));
    });
  }).then(function (csrPem) {
    return C.exportKey('pkcs8', pair.privateKey).then(function (p8) {
      if (!o.pass) return {csr: csrPem, key: derPem('PRIVATE KEY', new Uint8Array(p8))};
      return csrEncryptKey(new Uint8Array(p8), o.pass).then(function (enc) {
        return {csr: csrPem, key: derPem('ENCRYPTED PRIVATE KEY', enc)};
      });
    });
  });
}
/* PKCS#8 encrypted by PBES2 (PBKDF2-HMAC-SHA-256, AES-256-CBC) - openssl pkey -in KEY reads it */
function csrEncryptKey(p8, pass) {
  var C = window.crypto.subtle, salt = crypto.getRandomValues(new Uint8Array(16)), iv = crypto.getRandomValues(new Uint8Array(16));
  var iter = 600000;
  return C.importKey('raw', new TextEncoder().encode(pass), 'PBKDF2', false, ['deriveKey']).then(function (k) {
    return C.deriveKey({name: 'PBKDF2', salt: salt, iterations: iter, hash: 'SHA-256'}, k, {name: 'AES-CBC', length: 256}, false, ['encrypt']);
  }).then(function (aes) {
    return C.encrypt({name: 'AES-CBC', iv: iv}, aes, p8);
  }).then(function (ct) {
    var params = derSeq(
      derSeq(derOid(CSR_OID.pbkdf2), derSeq(derOctets(salt), derIntNum(iter), derSeq(derOid(CSR_OID.hmacSha256), [0x05, 0x00]))),
      derSeq(derOid(CSR_OID.aes256cbc), derOctets(iv)));
    return new Uint8Array(derSeq(derSeq(derOid(CSR_OID.pbes2), params), derOctets(new Uint8Array(ct))));
  });
}
