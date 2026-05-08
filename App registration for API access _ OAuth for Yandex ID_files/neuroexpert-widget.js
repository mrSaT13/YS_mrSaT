(function(){"use strict";try{if(typeof document<"u"){var e=document.createElement("style");e.appendChild(document.createTextNode('.iframe.svelte-149ck22{all:unset;width:100%;height:100%;display:block;z-index:var(--z-index)}.widget.svelte-149ck22{all:unset;visibility:hidden;width:368px;height:100%;border-radius:1.5rem;box-shadow:0 4px 4px 0 var(--fill-12);pointer-events:none}.widget.svelte-149ck22.visible{visibility:visible;pointer-events:all}@media (max-width: 768px){.widget.svelte-149ck22{width:100%}}@font-face{font-family:Neuroexpert-YS-Text;src:url(https://yastatic.net/s3/home/fonts/ys/4/text-regular.woff2) format("woff2"),url(https://yastatic.net/s3/home/fonts/ys/4/text-regular.woff) format("woff");font-weight:400;font-style:normal}.container.svelte-13k5vl5{--fill-6: #f0f0f0;--fill-9: #e8e8e8;--fill-12: rgba(0, 0, 0, .12);--text-primary: #000;--bg-primary: #fff;--bg-logo: #2b294f;box-sizing:border-box;padding:16px;height:100%;display:flex;flex-direction:column;gap:16px;align-items:flex-end;font-family:Neuroexpert-YS-Text,sans-serif;pointer-events:none;z-index:var(--z-index)}.container.svelte-13k5vl5.fixed{position:fixed;bottom:0;right:0}.container.svelte-13k5vl5 :where(.svelte-13k5vl5),.container.svelte-13k5vl5 :where(.svelte-13k5vl5):before,.container.svelte-13k5vl5 :where(.svelte-13k5vl5):after{box-sizing:inherit}.button-wrapper.svelte-13k5vl5{font-size:16px}.toggle-button.svelte-13k5vl5{all:unset;box-sizing:border-box;width:12em;height:3em;padding:.5em;display:flex;align-items:center;gap:.75em;background-color:var(--fill-6);border-radius:1.5em;cursor:pointer;transition:.2s;pointer-events:all}.toggle-button.svelte-13k5vl5:hover{background-color:var(--fill-9)}.logo-wrapper.svelte-13k5vl5{width:2em;height:2em;display:flex;align-items:center;justify-content:center;border-radius:50em;background-color:var(--bg-logo);pointer-events:none}.logo.svelte-13k5vl5,.custom-logo.svelte-13k5vl5{pointer-events:none}')),document.head.appendChild(e)}}catch(t){console.error("vite-plugin-css-injected-by-js",t)}})();
var mr = Object.defineProperty;
var yr = (e, t, r) => t in e ? mr(e, t, { enumerable: !0, configurable: !0, writable: !0, value: r }) : e[t] = r;
var Q = (e, t, r) => yr(e, typeof t != "symbol" ? t + "" : t, r);
var Et = Array.isArray, xr = Array.prototype.indexOf, Er = Array.from, Tr = Object.defineProperty, ie = Object.getOwnPropertyDescriptor, Tt = Object.getOwnPropertyDescriptors, Sr = Object.prototype, Cr = Array.prototype, Ke = Object.getPrototypeOf, lt = Object.isExtensible;
function Ir(e) {
  return e();
}
function qe(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
const F = 2, St = 4, Oe = 8, Ge = 16, H = 32, le = 64, Ee = 128, M = 256, Te = 512, D = 1024, B = 2048, ne = 4096, se = 8192, De = 16384, Rr = 32768, Ze = 65536, Or = 1 << 17, Dr = 1 << 19, Ct = 1 << 20, je = 1 << 21, $ = Symbol("$state"), Ar = Symbol("legacy props");
function It(e) {
  return e === this.v;
}
function kr(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function Je(e) {
  return !kr(e, this.v);
}
function Pr(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function Mr() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function Lr(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function Nr() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function Fr(e) {
  throw new Error("https://svelte.dev/e/props_invalid_value");
}
function qr() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function jr() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function Ur() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
let oe = !1;
function Wr() {
  oe = !0;
}
const Br = 1, Hr = 2, Vr = 4, Yr = 8, zr = 16, Kr = 2, O = Symbol(), Gr = "http://www.w3.org/1999/xhtml";
function Rt(e) {
  throw new Error("https://svelte.dev/e/lifecycle_outside_component");
}
let w = null;
function ot(e) {
  w = e;
}
function Ot(e, t = !1, r) {
  var n = w = {
    p: w,
    c: null,
    d: !1,
    e: null,
    m: !1,
    s: e,
    x: null,
    l: null
  };
  oe && !t && (w.l = {
    s: null,
    u: null,
    r1: [],
    r2: Xe(!1)
  }), Ut(() => {
    n.d = !0;
  });
}
function Dt(e) {
  const t = w;
  if (t !== null) {
    const o = t.e;
    if (o !== null) {
      var r = _, n = p;
      t.e = null;
      try {
        for (var a = 0; a < o.length; a++) {
          var i = o[a];
          G(i.effect), W(i.reaction), tt(i.fn);
        }
      } finally {
        G(r), W(n);
      }
    }
    w = t.p, t.m = !0;
  }
  return (
    /** @type {T} */
    {}
  );
}
function Ae() {
  return !oe || w !== null && w.l === null;
}
function X(e) {
  if (typeof e != "object" || e === null || $ in e)
    return e;
  const t = Ke(e);
  if (t !== Sr && t !== Cr)
    return e;
  var r = /* @__PURE__ */ new Map(), n = Et(e), a = /* @__PURE__ */ z(0), i = p, o = (u) => {
    var s = p;
    W(i);
    var l = u();
    return W(s), l;
  };
  return n && r.set("length", /* @__PURE__ */ z(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(u, s, l) {
        (!("value" in l) || l.configurable === !1 || l.enumerable === !1 || l.writable === !1) && qr();
        var d = r.get(s);
        return d === void 0 ? (d = o(() => /* @__PURE__ */ z(l.value)), r.set(s, d)) : I(
          d,
          o(() => X(l.value))
        ), !0;
      },
      deleteProperty(u, s) {
        var l = r.get(s);
        if (l === void 0)
          s in u && (r.set(
            s,
            o(() => /* @__PURE__ */ z(O))
          ), Ne(a));
        else {
          if (n && typeof s == "string") {
            var d = (
              /** @type {Source<number>} */
              r.get("length")
            ), c = Number(s);
            Number.isInteger(c) && c < d.v && I(d, c);
          }
          I(l, O), Ne(a);
        }
        return !0;
      },
      get(u, s, l) {
        var v;
        if (s === $)
          return e;
        var d = r.get(s), c = s in u;
        if (d === void 0 && (!c || (v = ie(u, s)) != null && v.writable) && (d = o(() => /* @__PURE__ */ z(X(c ? u[s] : O))), r.set(s, d)), d !== void 0) {
          var f = b(d);
          return f === O ? void 0 : f;
        }
        return Reflect.get(u, s, l);
      },
      getOwnPropertyDescriptor(u, s) {
        var l = Reflect.getOwnPropertyDescriptor(u, s);
        if (l && "value" in l) {
          var d = r.get(s);
          d && (l.value = b(d));
        } else if (l === void 0) {
          var c = r.get(s), f = c == null ? void 0 : c.v;
          if (c !== void 0 && f !== O)
            return {
              enumerable: !0,
              configurable: !0,
              value: f,
              writable: !0
            };
        }
        return l;
      },
      has(u, s) {
        var f;
        if (s === $)
          return !0;
        var l = r.get(s), d = l !== void 0 && l.v !== O || Reflect.has(u, s);
        if (l !== void 0 || _ !== null && (!d || (f = ie(u, s)) != null && f.writable)) {
          l === void 0 && (l = o(() => /* @__PURE__ */ z(d ? X(u[s]) : O)), r.set(s, l));
          var c = b(l);
          if (c === O)
            return !1;
        }
        return d;
      },
      set(u, s, l, d) {
        var j;
        var c = r.get(s), f = s in u;
        if (n && s === "length")
          for (var v = l; v < /** @type {Source<number>} */
          c.v; v += 1) {
            var g = r.get(v + "");
            g !== void 0 ? I(g, O) : v in u && (g = o(() => /* @__PURE__ */ z(O)), r.set(v + "", g));
          }
        c === void 0 ? (!f || (j = ie(u, s)) != null && j.writable) && (c = o(() => /* @__PURE__ */ z(void 0)), I(
          c,
          o(() => X(l))
        ), r.set(s, c)) : (f = c.v !== O, I(
          c,
          o(() => X(l))
        ));
        var m = Reflect.getOwnPropertyDescriptor(u, s);
        if (m != null && m.set && m.set.call(d, l), !f) {
          if (n && typeof s == "string") {
            var E = (
              /** @type {Source<number>} */
              r.get("length")
            ), A = Number(s);
            Number.isInteger(A) && A >= E.v && I(E, A + 1);
          }
          Ne(a);
        }
        return !0;
      },
      ownKeys(u) {
        b(a);
        var s = Reflect.ownKeys(u).filter((c) => {
          var f = r.get(c);
          return f === void 0 || f.v !== O;
        });
        for (var [l, d] of r)
          d.v !== O && !(l in u) && s.push(l);
        return s;
      },
      setPrototypeOf() {
        jr();
      }
    }
  );
}
function Ne(e, t = 1) {
  I(e, e.v + t);
}
// @__NO_SIDE_EFFECTS__
function ve(e) {
  var t = F | B, r = p !== null && (p.f & F) !== 0 ? (
    /** @type {Derived} */
    p
  ) : null;
  return _ === null || r !== null && (r.f & M) !== 0 ? t |= M : _.f |= Ct, {
    ctx: w,
    deps: null,
    effects: null,
    equals: It,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      null
    ),
    wv: 0,
    parent: r ?? _
  };
}
// @__NO_SIDE_EFFECTS__
function Qe(e) {
  const t = /* @__PURE__ */ ve(e);
  return t.equals = Je, t;
}
function At(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var r = 0; r < t.length; r += 1)
      te(
        /** @type {Effect} */
        t[r]
      );
  }
}
function Zr(e) {
  for (var t = e.parent; t !== null; ) {
    if ((t.f & F) === 0)
      return (
        /** @type {Effect} */
        t
      );
    t = t.parent;
  }
  return null;
}
function kt(e) {
  var t, r = _;
  G(Zr(e));
  try {
    At(e), t = $t(e);
  } finally {
    G(r);
  }
  return t;
}
function Pt(e) {
  var t = kt(e), r = (K || (e.f & M) !== 0) && e.deps !== null ? ne : D;
  q(e, r), e.equals(t) || (e.v = t, e.wv = Qt());
}
const he = /* @__PURE__ */ new Map();
function Xe(e, t) {
  var r = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: It,
    rv: 0,
    wv: 0
  };
  return r;
}
// @__NO_SIDE_EFFECTS__
function z(e, t) {
  const r = Xe(e);
  return un(r), r;
}
// @__NO_SIDE_EFFECTS__
function me(e, t = !1) {
  var n;
  const r = Xe(e);
  return t || (r.equals = Je), oe && w !== null && w.l !== null && ((n = w.l).s ?? (n.s = [])).push(r), r;
}
function Jr(e, t) {
  return I(
    e,
    re(() => b(e))
  ), t;
}
function I(e, t, r = !1) {
  p !== null && !U && Ae() && (p.f & (F | Ge)) !== 0 && !(R != null && R.includes(e)) && Ur();
  let n = r ? X(t) : t;
  return Qr(e, n);
}
function Qr(e, t) {
  if (!e.equals(t)) {
    var r = e.v;
    pe ? he.set(e, t) : he.set(e, r), e.v = t, (e.f & F) !== 0 && ((e.f & B) !== 0 && kt(
      /** @type {Derived} */
      e
    ), q(e, (e.f & M) === 0 ? D : ne)), e.wv = Qt(), Mt(e, B), Ae() && _ !== null && (_.f & D) !== 0 && (_.f & (H | le)) === 0 && (N === null ? fn([e]) : N.push(e));
  }
  return t;
}
function Mt(e, t) {
  var r = e.reactions;
  if (r !== null)
    for (var n = Ae(), a = r.length, i = 0; i < a; i++) {
      var o = r[i], u = o.f;
      (u & B) === 0 && (!n && o === _ || (q(o, t), (u & (D | M)) !== 0 && ((u & F) !== 0 ? Mt(
        /** @type {Derived} */
        o,
        ne
      ) : Pe(
        /** @type {Effect} */
        o
      ))));
    }
}
var Ue, Lt, Nt, Ft;
function Xr() {
  if (Ue === void 0) {
    Ue = window, Lt = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, r = Text.prototype;
    Nt = ie(t, "firstChild").get, Ft = ie(t, "nextSibling").get, lt(e) && (e.__click = void 0, e.__className = void 0, e.__attributes = null, e.__style = void 0, e.__e = void 0), lt(r) && (r.__t = void 0);
  }
}
function qt(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function $e(e) {
  return Nt.call(e);
}
// @__NO_SIDE_EFFECTS__
function et(e) {
  return Ft.call(e);
}
function we(e, t) {
  return /* @__PURE__ */ $e(e);
}
function $r(e, t) {
  {
    var r = (
      /** @type {DocumentFragment} */
      /* @__PURE__ */ $e(
        /** @type {Node} */
        e
      )
    );
    return r instanceof Comment && r.data === "" ? /* @__PURE__ */ et(r) : r;
  }
}
function en(e, t = 1, r = !1) {
  let n = e;
  for (; t--; )
    n = /** @type {TemplateNode} */
    /* @__PURE__ */ et(n);
  return n;
}
function jt(e) {
  _ === null && p === null && Lr(), p !== null && (p.f & M) !== 0 && _ === null && Mr(), pe && Pr();
}
function tn(e, t) {
  var r = t.last;
  r === null ? t.last = t.first = e : (r.next = e, e.prev = r, t.last = e);
}
function ue(e, t, r, n = !0) {
  var a = _, i = {
    ctx: w,
    deps: null,
    nodes_start: null,
    nodes_end: null,
    f: e | B,
    first: null,
    fn: t,
    last: null,
    next: null,
    parent: a,
    prev: null,
    teardown: null,
    transitions: null,
    wv: 0
  };
  if (r)
    try {
      rt(i), i.f |= Rr;
    } catch (s) {
      throw te(i), s;
    }
  else t !== null && Pe(i);
  var o = r && i.deps === null && i.first === null && i.nodes_start === null && i.teardown === null && (i.f & (Ct | Ee)) === 0;
  if (!o && n && (a !== null && tn(i, a), p !== null && (p.f & F) !== 0)) {
    var u = (
      /** @type {Derived} */
      p
    );
    (u.effects ?? (u.effects = [])).push(i);
  }
  return i;
}
function Ut(e) {
  const t = ue(Oe, null, !1);
  return q(t, D), t.teardown = e, t;
}
function We(e) {
  jt();
  var t = _ !== null && (_.f & H) !== 0 && w !== null && !w.m;
  if (t) {
    var r = (
      /** @type {ComponentContext} */
      w
    );
    (r.e ?? (r.e = [])).push({
      fn: e,
      effect: _,
      reaction: p
    });
  } else {
    var n = tt(e);
    return n;
  }
}
function rn(e) {
  return jt(), Wt(e);
}
function nn(e) {
  const t = ue(le, e, !0);
  return (r = {}) => new Promise((n) => {
    r.outro ? He(t, () => {
      te(t), n(void 0);
    }) : (te(t), n(void 0));
  });
}
function tt(e) {
  return ue(St, e, !1);
}
function Wt(e) {
  return ue(Oe, e, !0);
}
function Bt(e, t = [], r = ve) {
  const n = t.map(r);
  return Ht(() => e(...n.map(b)));
}
function Ht(e, t = 0) {
  return ue(Oe | Ge | t, e, !0);
}
function Be(e, t = !0) {
  return ue(Oe | H, e, !0, t);
}
function Vt(e) {
  var t = e.teardown;
  if (t !== null) {
    const r = pe, n = p;
    ft(!0), W(null);
    try {
      t.call(null);
    } finally {
      ft(r), W(n);
    }
  }
}
function Yt(e, t = !1) {
  var r = e.first;
  for (e.first = e.last = null; r !== null; ) {
    var n = r.next;
    (r.f & le) !== 0 ? r.parent = null : te(r, t), r = n;
  }
}
function an(e) {
  for (var t = e.first; t !== null; ) {
    var r = t.next;
    (t.f & H) === 0 && te(t), t = r;
  }
}
function te(e, t = !0) {
  var r = !1;
  (t || (e.f & Dr) !== 0) && e.nodes_start !== null && (sn(
    e.nodes_start,
    /** @type {TemplateNode} */
    e.nodes_end
  ), r = !0), Yt(e, t && !r), Re(e, 0), q(e, De);
  var n = e.transitions;
  if (n !== null)
    for (const i of n)
      i.stop();
  Vt(e);
  var a = e.parent;
  a !== null && a.first !== null && zt(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes_start = e.nodes_end = null;
}
function sn(e, t) {
  for (; e !== null; ) {
    var r = e === t ? null : (
      /** @type {TemplateNode} */
      /* @__PURE__ */ et(e)
    );
    e.remove(), e = r;
  }
}
function zt(e) {
  var t = e.parent, r = e.prev, n = e.next;
  r !== null && (r.next = n), n !== null && (n.prev = r), t !== null && (t.first === e && (t.first = n), t.last === e && (t.last = r));
}
function He(e, t) {
  var r = [];
  Kt(e, r, !0), ln(r, () => {
    te(e), t && t();
  });
}
function ln(e, t) {
  var r = e.length;
  if (r > 0) {
    var n = () => --r || t();
    for (var a of e)
      a.out(n);
  } else
    t();
}
function Kt(e, t, r) {
  if ((e.f & se) === 0) {
    if (e.f ^= se, e.transitions !== null)
      for (const o of e.transitions)
        (o.is_global || r) && t.push(o);
    for (var n = e.first; n !== null; ) {
      var a = n.next, i = (n.f & Ze) !== 0 || (n.f & H) !== 0;
      Kt(n, t, i ? r : !1), n = a;
    }
  }
}
function ut(e) {
  Gt(e, !0);
}
function Gt(e, t) {
  if ((e.f & se) !== 0) {
    e.f ^= se, (e.f & D) === 0 && (e.f ^= D), _e(e) && (q(e, B), Pe(e));
    for (var r = e.first; r !== null; ) {
      var n = r.next, a = (r.f & Ze) !== 0 || (r.f & H) !== 0;
      Gt(r, a ? t : !1), r = n;
    }
    if (e.transitions !== null)
      for (const i of e.transitions)
        (i.is_global || t) && i.in();
  }
}
let Se = [];
function on() {
  var e = Se;
  Se = [], qe(e);
}
function Zt(e) {
  Se.length === 0 && queueMicrotask(on), Se.push(e);
}
let ye = !1, Ve = !1, Ce = null, ee = !1, pe = !1;
function ft(e) {
  pe = e;
}
let xe = [];
let p = null, U = !1;
function W(e) {
  p = e;
}
let _ = null;
function G(e) {
  _ = e;
}
let R = null;
function un(e) {
  p !== null && p.f & je && (R === null ? R = [e] : R.push(e));
}
let C = null, P = 0, N = null;
function fn(e) {
  N = e;
}
let Jt = 1, Ie = 0, K = !1;
function Qt() {
  return ++Jt;
}
function _e(e) {
  var c;
  var t = e.f;
  if ((t & B) !== 0)
    return !0;
  if ((t & ne) !== 0) {
    var r = e.deps, n = (t & M) !== 0;
    if (r !== null) {
      var a, i, o = (t & Te) !== 0, u = n && _ !== null && !K, s = r.length;
      if (o || u) {
        var l = (
          /** @type {Derived} */
          e
        ), d = l.parent;
        for (a = 0; a < s; a++)
          i = r[a], (o || !((c = i == null ? void 0 : i.reactions) != null && c.includes(l))) && (i.reactions ?? (i.reactions = [])).push(l);
        o && (l.f ^= Te), u && d !== null && (d.f & M) === 0 && (l.f ^= M);
      }
      for (a = 0; a < s; a++)
        if (i = r[a], _e(
          /** @type {Derived} */
          i
        ) && Pt(
          /** @type {Derived} */
          i
        ), i.wv > e.wv)
          return !0;
    }
    (!n || _ !== null && !K) && q(e, D);
  }
  return !1;
}
function cn(e, t) {
  for (var r = t; r !== null; ) {
    if ((r.f & Ee) !== 0)
      try {
        r.fn(e);
        return;
      } catch {
        r.f ^= Ee;
      }
    r = r.parent;
  }
  throw ye = !1, e;
}
function ct(e) {
  return (e.f & De) === 0 && (e.parent === null || (e.parent.f & Ee) === 0);
}
function ke(e, t, r, n) {
  if (ye) {
    if (r === null && (ye = !1), ct(t))
      throw e;
    return;
  }
  if (r !== null && (ye = !0), cn(e, t), ct(t))
    throw e;
}
function Xt(e, t, r = !0) {
  var n = e.reactions;
  if (n !== null)
    for (var a = 0; a < n.length; a++) {
      var i = n[a];
      R != null && R.includes(e) || ((i.f & F) !== 0 ? Xt(
        /** @type {Derived} */
        i,
        t,
        !1
      ) : t === i && (r ? q(i, B) : (i.f & D) !== 0 && q(i, ne), Pe(
        /** @type {Effect} */
        i
      )));
    }
}
function $t(e) {
  var v;
  var t = C, r = P, n = N, a = p, i = K, o = R, u = w, s = U, l = e.f;
  C = /** @type {null | Value[]} */
  null, P = 0, N = null, K = (l & M) !== 0 && (U || !ee || p === null), p = (l & (H | le)) === 0 ? e : null, R = null, ot(e.ctx), U = !1, Ie++, e.f |= je;
  try {
    var d = (
      /** @type {Function} */
      (0, e.fn)()
    ), c = e.deps;
    if (C !== null) {
      var f;
      if (Re(e, P), c !== null && P > 0)
        for (c.length = P + C.length, f = 0; f < C.length; f++)
          c[P + f] = C[f];
      else
        e.deps = c = C;
      if (!K)
        for (f = P; f < c.length; f++)
          ((v = c[f]).reactions ?? (v.reactions = [])).push(e);
    } else c !== null && P < c.length && (Re(e, P), c.length = P);
    if (Ae() && N !== null && !U && c !== null && (e.f & (F | ne | B)) === 0)
      for (f = 0; f < /** @type {Source[]} */
      N.length; f++)
        Xt(
          N[f],
          /** @type {Effect} */
          e
        );
    return a !== null && a !== e && (Ie++, N !== null && (n === null ? n = N : n.push(.../** @type {Source[]} */
    N))), d;
  } finally {
    C = t, P = r, N = n, p = a, K = i, R = o, ot(u), U = s, e.f ^= je;
  }
}
function dn(e, t) {
  let r = t.reactions;
  if (r !== null) {
    var n = xr.call(r, e);
    if (n !== -1) {
      var a = r.length - 1;
      a === 0 ? r = t.reactions = null : (r[n] = r[a], r.pop());
    }
  }
  r === null && (t.f & F) !== 0 && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (C === null || !C.includes(t)) && (q(t, ne), (t.f & (M | Te)) === 0 && (t.f ^= Te), At(
    /** @type {Derived} **/
    t
  ), Re(
    /** @type {Derived} **/
    t,
    0
  ));
}
function Re(e, t) {
  var r = e.deps;
  if (r !== null)
    for (var n = t; n < r.length; n++)
      dn(e, r[n]);
}
function rt(e) {
  var t = e.f;
  if ((t & De) === 0) {
    q(e, D);
    var r = _, n = w, a = ee;
    _ = e, ee = !0;
    try {
      (t & Ge) !== 0 ? an(e) : Yt(e), Vt(e);
      var i = $t(e);
      e.teardown = typeof i == "function" ? i : null, e.wv = Jt;
      var o = e.deps, u;
    } catch (s) {
      ke(s, e, r, n || e.ctx);
    } finally {
      ee = a, _ = r;
    }
  }
}
function vn() {
  try {
    Nr();
  } catch (e) {
    if (Ce !== null)
      ke(e, Ce, null);
    else
      throw e;
  }
}
function hn() {
  var e = ee;
  try {
    var t = 0;
    for (ee = !0; xe.length > 0; ) {
      t++ > 1e3 && vn();
      var r = xe, n = r.length;
      xe = [];
      for (var a = 0; a < n; a++) {
        var i = _n(r[a]);
        pn(i);
      }
      he.clear();
    }
  } finally {
    Ve = !1, ee = e, Ce = null;
  }
}
function pn(e) {
  var t = e.length;
  if (t !== 0)
    for (var r = 0; r < t; r++) {
      var n = e[r];
      if ((n.f & (De | se)) === 0)
        try {
          _e(n) && (rt(n), n.deps === null && n.first === null && n.nodes_start === null && (n.teardown === null ? zt(n) : n.fn = null));
        } catch (a) {
          ke(a, n, null, n.ctx);
        }
    }
}
function Pe(e) {
  Ve || (Ve = !0, queueMicrotask(hn));
  for (var t = Ce = e; t.parent !== null; ) {
    t = t.parent;
    var r = t.f;
    if ((r & (le | H)) !== 0) {
      if ((r & D) === 0) return;
      t.f ^= D;
    }
  }
  xe.push(t);
}
function _n(e) {
  for (var t = [], r = e; r !== null; ) {
    var n = r.f, a = (n & (H | le)) !== 0, i = a && (n & D) !== 0;
    if (!i && (n & se) === 0) {
      if ((n & St) !== 0)
        t.push(r);
      else if (a)
        r.f ^= D;
      else
        try {
          _e(r) && rt(r);
        } catch (s) {
          ke(s, r, null, r.ctx);
        }
      var o = r.first;
      if (o !== null) {
        r = o;
        continue;
      }
    }
    var u = r.parent;
    for (r = r.next; r === null && u !== null; )
      r = u.next, u = u.parent;
  }
  return t;
}
function b(e) {
  var t = e.f, r = (t & F) !== 0;
  if (p !== null && !U) {
    if (!(R != null && R.includes(e))) {
      var n = p.deps;
      e.rv < Ie && (e.rv = Ie, C === null && n !== null && n[P] === e ? P++ : C === null ? C = [e] : (!K || !C.includes(e)) && C.push(e));
    }
  } else if (r && /** @type {Derived} */
  e.deps === null && /** @type {Derived} */
  e.effects === null) {
    var a = (
      /** @type {Derived} */
      e
    ), i = a.parent;
    i !== null && (i.f & M) === 0 && (a.f ^= M);
  }
  return r && (a = /** @type {Derived} */
  e, _e(a) && Pt(a)), pe && he.has(e) ? he.get(e) : e.v;
}
function re(e) {
  var t = U;
  try {
    return U = !0, e();
  } finally {
    U = t;
  }
}
const gn = -7169;
function q(e, t) {
  e.f = e.f & gn | t;
}
function wn(e) {
  if (!(typeof e != "object" || !e || e instanceof EventTarget)) {
    if ($ in e)
      Ye(e);
    else if (!Array.isArray(e))
      for (let t in e) {
        const r = e[t];
        typeof r == "object" && r && $ in r && Ye(r);
      }
  }
}
function Ye(e, t = /* @__PURE__ */ new Set()) {
  if (typeof e == "object" && e !== null && // We don't want to traverse DOM elements
  !(e instanceof EventTarget) && !t.has(e)) {
    t.add(e), e instanceof Date && e.getTime();
    for (let n in e)
      try {
        Ye(e[n], t);
      } catch {
      }
    const r = Ke(e);
    if (r !== Object.prototype && r !== Array.prototype && r !== Map.prototype && r !== Set.prototype && r !== Date.prototype) {
      const n = Tt(r);
      for (let a in n) {
        const i = n[a].get;
        if (i)
          try {
            i.call(e);
          } catch {
          }
      }
    }
  }
}
const bn = ["touchstart", "touchmove"];
function mn(e) {
  return bn.includes(e);
}
function yn(e) {
  var t = p, r = _;
  W(null), G(null);
  try {
    return e();
  } finally {
    W(t), G(r);
  }
}
const er = /* @__PURE__ */ new Set(), ze = /* @__PURE__ */ new Set();
function xn(e, t, r, n = {}) {
  function a(i) {
    if (n.capture || ce.call(t, i), !i.cancelBubble)
      return yn(() => r == null ? void 0 : r.call(this, i));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? Zt(() => {
    t.addEventListener(e, a, n);
  }) : t.addEventListener(e, a, n), a;
}
function En(e, t, r, n, a) {
  var i = { capture: n, passive: a }, o = xn(e, t, r, i);
  (t === document.body || t === window || t === document) && Ut(() => {
    t.removeEventListener(e, o, i);
  });
}
function Tn(e) {
  for (var t = 0; t < e.length; t++)
    er.add(e[t]);
  for (var r of ze)
    r(e);
}
function ce(e) {
  var j;
  var t = this, r = (
    /** @type {Node} */
    t.ownerDocument
  ), n = e.type, a = ((j = e.composedPath) == null ? void 0 : j.call(e)) || [], i = (
    /** @type {null | Element} */
    a[0] || e.target
  ), o = 0, u = e.__root;
  if (u) {
    var s = a.indexOf(u);
    if (s !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e.__root = t;
      return;
    }
    var l = a.indexOf(t);
    if (l === -1)
      return;
    s <= l && (o = s);
  }
  if (i = /** @type {Element} */
  a[o] || e.target, i !== t) {
    Tr(e, "currentTarget", {
      configurable: !0,
      get() {
        return i || r;
      }
    });
    var d = p, c = _;
    W(null), G(null);
    try {
      for (var f, v = []; i !== null; ) {
        var g = i.assignedSlot || i.parentNode || /** @type {any} */
        i.host || null;
        try {
          var m = i["__" + n];
          if (m != null && (!/** @type {any} */
          i.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === i))
            if (Et(m)) {
              var [E, ...A] = m;
              E.apply(i, [e, ...A]);
            } else
              m.call(i, e);
        } catch (T) {
          f ? v.push(T) : f = T;
        }
        if (e.cancelBubble || g === t || g === null)
          break;
        i = g;
      }
      if (f) {
        for (let T of v)
          queueMicrotask(() => {
            throw T;
          });
        throw f;
      }
    } finally {
      e.__root = t, delete e.currentTarget, W(d), G(c);
    }
  }
}
function Sn(e) {
  var t = document.createElement("template");
  return t.innerHTML = e, t.content;
}
function tr(e, t) {
  var r = (
    /** @type {Effect} */
    _
  );
  r.nodes_start === null && (r.nodes_start = e, r.nodes_end = t);
}
// @__NO_SIDE_EFFECTS__
function Me(e, t) {
  var r = (t & Kr) !== 0, n, a = !e.startsWith("<!>");
  return () => {
    n === void 0 && (n = Sn(a ? e : "<!>" + e), n = /** @type {Node} */
    /* @__PURE__ */ $e(n));
    var i = (
      /** @type {TemplateNode} */
      r || Lt ? document.importNode(n, !0) : n.cloneNode(!0)
    );
    return tr(i, i), i;
  };
}
function Cn() {
  var e = document.createDocumentFragment(), t = document.createComment(""), r = qt();
  return e.append(t, r), tr(t, r), e;
}
function de(e, t) {
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
function In(e, t) {
  return Rn(e, t);
}
const ae = /* @__PURE__ */ new Map();
function Rn(e, { target: t, anchor: r, props: n = {}, events: a, context: i, intro: o = !0 }) {
  Xr();
  var u = /* @__PURE__ */ new Set(), s = (c) => {
    for (var f = 0; f < c.length; f++) {
      var v = c[f];
      if (!u.has(v)) {
        u.add(v);
        var g = mn(v);
        t.addEventListener(v, ce, { passive: g });
        var m = ae.get(v);
        m === void 0 ? (document.addEventListener(v, ce, { passive: g }), ae.set(v, 1)) : ae.set(v, m + 1);
      }
    }
  };
  s(Er(er)), ze.add(s);
  var l = void 0, d = nn(() => {
    var c = r ?? t.appendChild(qt());
    return Be(() => {
      if (i) {
        Ot({});
        var f = (
          /** @type {ComponentContext} */
          w
        );
        f.c = i;
      }
      a && (n.$$events = a), l = e(c, n) || {}, i && Dt();
    }), () => {
      var g;
      for (var f of u) {
        t.removeEventListener(f, ce);
        var v = (
          /** @type {number} */
          ae.get(f)
        );
        --v === 0 ? (document.removeEventListener(f, ce), ae.delete(f)) : ae.set(f, v);
      }
      ze.delete(s), c !== r && ((g = c.parentNode) == null || g.removeChild(c));
    };
  });
  return On.set(l, d), l;
}
let On = /* @__PURE__ */ new WeakMap();
function dt(e, t, [r, n] = [0, 0]) {
  var a = e, i = null, o = null, u = O, s = r > 0 ? Ze : 0, l = !1;
  const d = (f, v = !0) => {
    l = !0, c(v, f);
  }, c = (f, v) => {
    u !== (u = f) && (u ? (i ? ut(i) : v && (i = Be(() => v(a))), o && He(o, () => {
      o = null;
    })) : (o ? ut(o) : v && (o = Be(() => v(a, [r + 1, n]))), i && He(i, () => {
      i = null;
    })));
  };
  Ht(() => {
    l = !1, t(d), l || c(null, null);
  }, s);
}
function rr(e) {
  var t, r, n = "";
  if (typeof e == "string" || typeof e == "number") n += e;
  else if (typeof e == "object") if (Array.isArray(e)) {
    var a = e.length;
    for (t = 0; t < a; t++) e[t] && (r = rr(e[t])) && (n && (n += " "), n += r);
  } else for (r in e) e[r] && (n && (n += " "), n += r);
  return n;
}
function Dn() {
  for (var e, t, r = 0, n = "", a = arguments.length; r < a; r++) (e = arguments[r]) && (t = rr(e)) && (n && (n += " "), n += t);
  return n;
}
function An(e) {
  return typeof e == "object" ? Dn(e) : e ?? "";
}
const vt = [...` 	
\r\f \v\uFEFF`];
function kn(e, t, r) {
  var n = e == null ? "" : "" + e;
  if (t && (n = n ? n + " " + t : t), r) {
    for (var a in r)
      if (r[a])
        n = n ? n + " " + a : a;
      else if (n.length)
        for (var i = a.length, o = 0; (o = n.indexOf(a, o)) >= 0; ) {
          var u = o + i;
          (o === 0 || vt.includes(n[o - 1])) && (u === n.length || vt.includes(n[u])) ? n = (o === 0 ? "" : n.substring(0, o)) + n.substring(u + 1) : o = u;
        }
  }
  return n === "" ? null : n;
}
function ht(e, t = !1) {
  var r = t ? " !important;" : ";", n = "";
  for (var a in e) {
    var i = e[a];
    i != null && i !== "" && (n += " " + a + ": " + i + r);
  }
  return n;
}
function Pn(e, t) {
  if (t) {
    var r = "", n, a;
    return Array.isArray(t) ? (n = t[0], a = t[1]) : n = t, n && (r += ht(n)), a && (r += ht(a, !0)), r = r.trim(), r === "" ? null : r;
  }
  return String(e);
}
function nr(e, t, r, n, a, i) {
  var o = e.__className;
  if (o !== r || o === void 0) {
    var u = kn(r, n, i);
    u == null ? e.removeAttribute("class") : e.className = u, e.__className = r;
  } else if (i && a !== i)
    for (var s in i) {
      var l = !!i[s];
      (a == null || l !== !!a[s]) && e.classList.toggle(s, l);
    }
  return i;
}
function Fe(e, t = {}, r, n) {
  for (var a in r) {
    var i = r[a];
    t[a] !== i && (r[a] == null ? e.style.removeProperty(a) : e.style.setProperty(a, i, n));
  }
}
function ar(e, t, r, n) {
  var a = e.__style;
  if (a !== t) {
    var i = Pn(t, n);
    i == null ? e.removeAttribute("style") : e.style.cssText = i, e.__style = t;
  } else n && (Array.isArray(n) ? (Fe(e, r == null ? void 0 : r[0], n[0]), Fe(e, r == null ? void 0 : r[1], n[1], "important")) : Fe(e, r, n));
  return n;
}
const Mn = Symbol("is custom element"), Ln = Symbol("is html");
function pt(e, t, r, n) {
  var a = Nn(e);
  a[t] !== (a[t] = r) && (r == null ? e.removeAttribute(t) : typeof r != "string" && Fn(e).includes(t) ? e[t] = r : e.setAttribute(t, r));
}
function Nn(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    // @ts-expect-error
    e.__attributes ?? (e.__attributes = {
      [Mn]: e.nodeName.includes("-"),
      [Ln]: e.namespaceURI === Gr
    })
  );
}
var _t = /* @__PURE__ */ new Map();
function Fn(e) {
  var t = _t.get(e.nodeName);
  if (t) return t;
  _t.set(e.nodeName, t = []);
  for (var r, n = e, a = Element.prototype; a !== n; ) {
    r = Tt(n);
    for (var i in r)
      r[i].set && t.push(i);
    n = Ke(n);
  }
  return t;
}
function gt(e, t) {
  return e === t || (e == null ? void 0 : e[$]) === t;
}
function ir(e = {}, t, r, n) {
  return tt(() => {
    var a, i;
    return Wt(() => {
      a = i, i = [], re(() => {
        e !== r(...i) && (t(e, ...i), a && gt(r(...a), e) && t(null, ...a));
      });
    }), () => {
      Zt(() => {
        i && gt(r(...i), e) && t(null, ...i);
      });
    };
  }), e;
}
function qn(e = !1) {
  const t = (
    /** @type {ComponentContextLegacy} */
    w
  ), r = t.l.u;
  if (!r) return;
  let n = () => wn(t.s);
  if (e) {
    let a = 0, i = (
      /** @type {Record<string, any>} */
      {}
    );
    const o = /* @__PURE__ */ ve(() => {
      let u = !1;
      const s = t.s;
      for (const l in s)
        s[l] !== i[l] && (i[l] = s[l], u = !0);
      return u && a++, a;
    });
    n = () => b(o);
  }
  r.b.length && rn(() => {
    wt(t, n), qe(r.b);
  }), We(() => {
    const a = re(() => r.m.map(Ir));
    return () => {
      for (const i of a)
        typeof i == "function" && i();
    };
  }), r.a.length && We(() => {
    wt(t, n), qe(r.a);
  });
}
function wt(e, t) {
  if (e.l.s)
    for (const r of e.l.s) b(r);
  t();
}
let be = !1;
function jn(e) {
  var t = be;
  try {
    return be = !1, [e(), be];
  } finally {
    be = t;
  }
}
function bt(e) {
  var t;
  return ((t = e.ctx) == null ? void 0 : t.d) ?? !1;
}
function x(e, t, r, n) {
  var V;
  var a = (r & Br) !== 0, i = !oe || (r & Hr) !== 0, o = (r & Yr) !== 0, u = (r & zr) !== 0, s = !1, l;
  o ? [l, s] = jn(() => (
    /** @type {V} */
    e[t]
  )) : l = /** @type {V} */
  e[t];
  var d = $ in e || Ar in e, c = o && (((V = ie(e, t)) == null ? void 0 : V.set) ?? (d && t in e && ((y) => e[t] = y))) || void 0, f = (
    /** @type {V} */
    n
  ), v = !0, g = !1, m = () => (g = !0, v && (v = !1, u ? f = re(
    /** @type {() => V} */
    n
  ) : f = /** @type {V} */
  n), f);
  l === void 0 && n !== void 0 && (c && i && Fr(), l = m(), c && c(l));
  var E;
  if (i)
    E = () => {
      var y = (
        /** @type {V} */
        e[t]
      );
      return y === void 0 ? m() : (v = !0, g = !1, y);
    };
  else {
    var A = (a ? ve : Qe)(
      () => (
        /** @type {V} */
        e[t]
      )
    );
    A.f |= Or, E = () => {
      var y = b(A);
      return y !== void 0 && (f = /** @type {V} */
      void 0), y === void 0 ? f : y;
    };
  }
  if ((r & Vr) === 0)
    return E;
  if (c) {
    var j = e.$$legacy;
    return function(y, J) {
      return arguments.length > 0 ? ((!i || !J || j || s) && c(J ? E() : y), y) : E();
    };
  }
  var T = !1, Z = /* @__PURE__ */ me(l), k = /* @__PURE__ */ ve(() => {
    var y = E(), J = b(Z);
    return T ? (T = !1, J) : Z.v = y;
  });
  return o && b(k), a || (k.equals = Je), function(y, J) {
    if (arguments.length > 0) {
      const Y = J ? b(k) : i && o ? X(y) : y;
      if (!k.equals(Y)) {
        if (T = !0, I(Z, Y), g && f !== void 0 && (f = Y), bt(k))
          return y;
        re(() => b(k));
      }
      return y;
    }
    return bt(k) ? k.v : b(k);
  };
}
function sr(e) {
  w === null && Rt(), oe && w.l !== null ? Wn(w).m.push(e) : We(() => {
    const t = re(e);
    if (typeof t == "function") return (
      /** @type {() => void} */
      t
    );
  });
}
function Un(e) {
  w === null && Rt(), sr(() => () => re(e));
}
function Wn(e) {
  var t = (
    /** @type {ComponentContextLegacy} */
    e.l
  );
  return t.u ?? (t.u = { a: [], b: [], m: [] });
}
const mt = "1.0", Bn = {
  canReadSelection: !1,
  canReadFullDocument: !1,
  canReadTrackChanges: !1,
  canReadComments: !1,
  canInsertText: !1,
  canInsertFormatted: !1,
  canAddComments: !1,
  canApplyRedlines: !1
};
function Hn(e) {
  const t = {
    ...Bn,
    ...e.capabilities
  };
  return Vn(t, e), {
    getCapabilities: () => t,
    getSelectedText: e.getSelectedText ? async () => e.getSelectedText() : void 0,
    getFullDocument: e.getFullDocument ? async () => e.getFullDocument() : void 0,
    getDocumentMetadata: e.getDocumentMetadata ? async () => e.getDocumentMetadata() : void 0,
    getTrackChanges: e.getTrackChanges ? async () => e.getTrackChanges() : void 0,
    getComments: e.getComments ? async () => e.getComments() : void 0,
    insertText: e.insertText ? async (r, n) => {
      await e.insertText(r, n);
    } : void 0,
    insertFormattedText: e.insertFormattedText ? async (r, n) => {
      await e.insertFormattedText(r, n);
    } : void 0,
    replaceSelection: e.replaceSelection ? async (r) => {
      await e.replaceSelection(r);
    } : void 0,
    addComment: e.addComment ? async (r, n) => {
      await e.addComment(r, n);
    } : void 0,
    applyRedlines: e.applyRedlines ? async (r) => {
      await e.applyRedlines(r);
    } : void 0,
    onSelectionChange: e.onSelectionChange
  };
}
function Vn(e, t) {
  const r = [
    ["canReadSelection", "getSelectedText"],
    ["canReadFullDocument", "getFullDocument"],
    ["canReadTrackChanges", "getTrackChanges"],
    ["canReadComments", "getComments"],
    ["canInsertText", "insertText"],
    ["canInsertFormatted", "insertFormattedText"],
    ["canAddComments", "addComment"],
    ["canApplyRedlines", "applyRedlines"]
  ];
  for (const [n, a] of r)
    e[n] && !t[a] && console.warn(
      `[NeurolegalSDK] Capability "${n}" is enabled but method "${a}" is not provided.`
    );
}
class Yn {
  constructor(t, r, n) {
    Q(this, "iframe");
    Q(this, "adapter");
    Q(this, "selectionUnsubscribe");
    Q(this, "isDestroyed", !1);
    Q(this, "widgetOrigin");
    Q(this, "handleMessage", async (t) => {
      if (this.isDestroyed || this.widgetOrigin && t.origin !== this.widgetOrigin) return;
      const r = t.data;
      !r || r.source !== "neurolegal-widget" || (r.type === "event" && this.handleWidgetEvent(r), r.type === "request" && await this.handleRequest(r));
    });
    this.iframe = t, this.adapter = r, this.widgetOrigin = n == null ? void 0 : n.widgetOrigin, window.addEventListener("message", this.handleMessage);
  }
  destroy() {
    var t;
    this.isDestroyed = !0, window.removeEventListener("message", this.handleMessage), (t = this.selectionUnsubscribe) == null || t.call(this);
  }
  sendEvent(t) {
    if (this.isDestroyed) return;
    const r = {
      source: "neurolegal-host",
      version: mt,
      type: "event",
      event: t
    };
    this.postToWidget(r);
  }
  handleWidgetEvent(t) {
    switch (t.event.name) {
      case "widgetReady":
        this.onWidgetReady();
        break;
    }
  }
  onWidgetReady() {
    this.sendEvent({
      name: "hostReady",
      data: { capabilities: this.adapter.getCapabilities() }
    }), this.setupSelectionTracking();
  }
  async handleRequest(t) {
    const { requestId: r, command: n } = t;
    try {
      const a = await this.executeCommand(n);
      this.sendResponse(r, !0, a);
    } catch (a) {
      const i = {
        code: "EXECUTION_ERROR",
        message: a instanceof Error ? a.message : "Unknown error"
      };
      this.sendResponse(r, !1, void 0, i);
    }
  }
  async executeCommand(t) {
    switch (t.name) {
      case "getCapabilities":
        return this.adapter.getCapabilities();
      case "getSelectedText":
        return this.assertMethod("getSelectedText"), this.adapter.getSelectedText();
      case "getFullDocument":
        return this.assertMethod("getFullDocument"), this.adapter.getFullDocument();
      case "getDocumentMetadata":
        return this.assertMethod("getDocumentMetadata"), this.adapter.getDocumentMetadata();
      case "getTrackChanges":
        return this.assertMethod("getTrackChanges"), this.adapter.getTrackChanges();
      case "getComments":
        return this.assertMethod("getComments"), this.adapter.getComments();
      case "insertText":
        return this.assertMethod("insertText"), this.adapter.insertText(
          t.params.text,
          t.params.position
        );
      case "insertFormattedText":
        return this.assertMethod("insertFormattedText"), this.adapter.insertFormattedText(
          t.params.text,
          t.params.preserveTargetStyle
        );
      case "replaceSelection":
        return this.assertMethod("replaceSelection"), this.adapter.replaceSelection(t.params.text);
      case "addComment":
        return this.assertMethod("addComment"), this.adapter.addComment(
          t.params.text,
          t.params.range
        );
      case "applyRedlines":
        return this.assertMethod("applyRedlines"), this.adapter.applyRedlines(t.params.changes);
      default:
        throw new Error(
          `Unknown command: ${t.name}`
        );
    }
  }
  assertMethod(t) {
    if (!this.adapter[t])
      throw new Error(
        `Method "${t}" is not supported by this adapter`
      );
  }
  sendResponse(t, r, n, a) {
    const i = {
      source: "neurolegal-host",
      version: mt,
      type: "response",
      requestId: t,
      success: r,
      data: n,
      error: a
    };
    this.postToWidget(i);
  }
  postToWidget(t) {
    var n;
    const r = this.widgetOrigin || "*";
    (n = this.iframe.contentWindow) == null || n.postMessage(t, r);
  }
  setupSelectionTracking() {
    this.adapter.onSelectionChange && (this.selectionUnsubscribe = this.adapter.onSelectionChange(
      (t, r) => {
        this.sendEvent({
          name: "selectionChanged",
          data: { text: t, range: r }
        });
      }
    ));
  }
}
const zn = "5";
var xt;
typeof window < "u" && ((xt = window.__svelte ?? (window.__svelte = {})).v ?? (xt.v = /* @__PURE__ */ new Set())).add(zn);
Wr();
const Kn = "data:image/svg+xml,%3csvg%20xmlns='http://www.w3.org/2000/svg'%20width='21'%20height='18'%20fill='none'%3e%3cpath%20fill='%23fff'%20fill-rule='evenodd'%20d='M5.314%203.3q1.003-.899%202.93-.898h.076l.025.001c.672.009%201.3.298%201.81.735.32.277.741.462%201.204.462a1.8%201.8%200%200%200%201.8-1.8c0-.957-.72-1.8-2.006-1.8H8.217Q4.786%200%202.991%201.61%201.224%203.219%201.223%205.833q0%201.478.502%202.613a7%207%200%200%200%201.451%202.058q.744.705%201.717%201.408L.801%2018h3.378l4.566-6.81-1.584-1.082q-1.451-.976-2.164-1.9-.686-.95-.686-2.56%200-1.451%201.003-2.349m11.337-1.55a1.25%201.25%200%201%201-2.5%200%201.25%201.25%200%200%201%202.5%200m2.75%200a.75.75%200%201%201-1.5%200%20.75.75%200%200%201%201.5%200m-6%204.775a1.875%201.875%200%201%201-3.75%200%201.875%201.875%200%200%201%203.75%200m4.25%200a1.5%201.5%200%201%201-3%200%201.5%201.5%200%200%201%203%200m2.25%201a1%201%200%201%200%200-2%201%201%200%200%200%200%202m-8.375%205.825a1.875%201.875%200%201%200%200-3.75%201.875%201.875%200%200%200%200%203.75m4.625-.375a1.5%201.5%200%201%200%200-3%201.5%201.5%200%200%200%200%203m4.75-1.5a1%201%200%201%201-2%200%201%201%200%200%201%202%200M11.4%2018a1.75%201.75%200%201%200%200-3.5%201.75%201.75%200%200%200%200%203.5m4-.5a1.25%201.25%200%201%200%200-2.5%201.25%201.25%200%200%200%200%202.5m4-1.25a.75.75%200%201%201-1.5%200%20.75.75%200%200%201%201.5%200'%20clip-rule='evenodd'/%3e%3c/svg%3e";
var Gn = /* @__PURE__ */ Me('<iframe title="neuroexpert-widget" src="about:blank" allow="clipboard-write"></iframe>');
function yt(e, t) {
  let r = x(t, "iframeElement", 12), n = x(t, "isIframe", 8, !1), a = x(t, "isOpen", 8, !0), i = x(t, "zIndex", 8, 1e3);
  var o = Gn();
  let u, s;
  ir(o, (l) => r(l), () => r()), Bt(
    (l) => {
      u = nr(o, 1, An(n() ? "iframe" : "widget"), "svelte-149ck22", u, l), s = ar(o, "", s, { "--z-index": i() });
    },
    [() => ({ visible: a() })],
    Qe
  ), de(e, o);
}
const Zn = (e, t) => {
  I(t, !b(t));
};
var Jn = /* @__PURE__ */ Me('<img class="custom-logo svelte-13k5vl5" width="32" height="32" alt="Logo">'), Qn = /* @__PURE__ */ Me('<span class="logo-wrapper svelte-13k5vl5"><img class="logo svelte-13k5vl5" width="20" height="16" alt="Logo"></span>'), Xn = /* @__PURE__ */ Me('<div><!> <div class="button-wrapper svelte-13k5vl5"><button class="toggle-button svelte-13k5vl5"><!> Нужна помощь?</button></div></div>');
function $n(e, t) {
  Ot(t, !1);
  const r = ["by", "ru"];
  let n = x(t, "consumer", 8, void 0), a = x(t, "projectId", 8, void 0), i = x(t, "hasOutsideClick", 8, !0), o = x(t, "isIframe", 8, !1), u = x(t, "isInternal", 8, !1), s = x(t, "parentId", 8, void 0), l = x(t, "platform", 8, void 0), d = x(t, "zIndex", 8, 1e3), c = x(t, "uid", 8, void 0), f = x(t, "theme", 8, "auto"), v = x(t, "tld", 8, void 0), g = x(t, "customLabel", 8, void 0), m = x(t, "hasHeader", 8, !1), E = x(t, "beta", 8, !1), A = x(t, "customOrigin", 8, void 0), j = x(t, "adapter", 8, void 0), T = /* @__PURE__ */ me(), Z = /* @__PURE__ */ me(!1), k = /* @__PURE__ */ me(), V = null;
  const y = () => {
    if (v() && r.includes(v()))
      return v();
    const h = window.location.origin.split(".").pop();
    return h && r.includes(h) ? h : "ru";
  }, Y = A() ? A() : u() ? "https://expert.yandex-team.ru" : n() ? `https://alicepro.yandex.${y()}` : "https://expert.yandex.ru", lr = (h) => {
    !i() || o() || h.target !== b(k) && I(Z, !1);
  }, or = (h) => {
    const S = new Uint8Array(h);
    return window.crypto.getRandomValues(S), Array.from(S, (ge) => ge.toString(16).padStart(2, "0")).join("");
  }, ur = () => {
    const h = localStorage.getItem("neuroexpert-user-salt");
    if (h) return h;
    const S = or(16);
    return localStorage.setItem("neuroexpert-user-salt", S), S;
  }, fr = () => a() ? n() ? `${Y}/expert/projects/${a()}/iframe-boltalka` : `${Y}/expert/projects/${a()}/${o() ? "iframe" : "widget"}` : `${Y}/expert/iframe-boltalka`, cr = () => {
    const h = new URL(fr());
    return f() !== "auto" && h.searchParams.set("theme", f()), a() && h.searchParams.set("userSalt", ur()), n() && h.searchParams.set("consumer", n()), l() && h.searchParams.set("platform", l()), c() && h.searchParams.set("uid", c()), g() && h.searchParams.set("customLabel", g()), m() && h.searchParams.set("hasHeader", String(m())), E() && h.searchParams.set("beta", String(E())), h.toString();
  }, nt = (() => {
    var h;
    if (g() && a())
      try {
        return (h = JSON.parse(`{
  "production": {
    "54f6f5e30bf811f19435fe681ff4b802": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/star.png",
    "8f0afa2458d011f0b81a2adde7e90ca6": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/alice-devices.svg",
    "a91b9a88a5c511f09524261771723f18": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/corp-bro.svg",
    "e8b0fdbe3c9311f0a45aa6ff32bd5860": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/history.ru.png",
    "e5a66bca8d9711f0991776989734f535": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/alice-pro.png",
    "dbf67ea3d5ce11f086bd261771723f18": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/support.svg",
    "12f4ab2c0d9c11f18d682e7dfacf48ee": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/support.svg",
    "4eb5dd940cc411f1bbb8c2e3e0e0ab3c": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/trans-russia.png",
    "f9176e3ed03311f0a5db8e7d0d775479": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/rsk.svg",
    "db57349f9d5811f0bd52eab7ff754a80": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/perco.png",
    "17ebf312d5bb11f08aaf52372231acfc": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/ai-ico-chat.png",
    "2e5e9ce33f1911f1b3b3ceeb90a42f72": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/femida.svg",
    "5ade09d83da511f1b69ccaa3c2be664f": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/deer.svg"
  },
  "testing": {
    "822c38217f5811f098fe2aa6398a8adf": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/history.ru.png",
    "6bba7e10b25b11f08f889201b50f60c8": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/alice-pro.png",
    "38dbe3e0df5411f0ac809201b50f60c8": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/support.svg",
    "82eaf24fa3bb11f08ee89201b50f60c8": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/star.png",
    "17ebf312d5bb11f08aaf52372231acfc": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/ai-ico-chat.png"
  },
  "development": {
    "822c38217f5811f098fe2aa6398a8adf": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/history.ru.png",
    "6bba7e10b25b11f08f889201b50f60c8": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/alice-pro.png",
    "38dbe3e0df5411f0ac809201b50f60c8": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/support.svg",
    "82eaf24fa3bb11f08ee89201b50f60c8": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/deer.svg",
    "17ebf312d5bb11f08aaf52372231acfc": "https://browserweb.s3.yandex.net/neuro-expert/widget-white-label-icons/ai-ico-chat.png"
  }
}
`).production) == null ? void 0 : h[a()];
      } catch (S) {
        console.error(new Error("Failed to get custom logo from whitelabel projects list", { cause: S }));
      }
  })();
  sr(() => {
    Jr(T, b(T).src = cr()), j() && (V = new Yn(b(T), j(), { widgetOrigin: Y }));
  }), Un(() => {
    V == null || V.destroy(), V = null;
  }), qn();
  var at = Cn();
  En("click", Ue, lr);
  var dr = $r(at);
  {
    var vr = (h) => {
      yt(h, {
        isIframe: !0,
        get zIndex() {
          return d();
        },
        get iframeElement() {
          return b(T);
        },
        set iframeElement(S) {
          I(T, S);
        },
        $$legacy: !0
      });
    }, hr = (h) => {
      var S = Xn();
      let ge, it;
      var st = we(S);
      yt(st, {
        get isOpen() {
          return b(Z);
        },
        get iframeElement() {
          return b(T);
        },
        set iframeElement(L) {
          I(T, L);
        },
        $$legacy: !0
      });
      var pr = en(st, 2), Le = we(pr);
      Le.__click = [Zn, Z];
      var _r = we(Le);
      {
        var gr = (L) => {
          var fe = Jn();
          pt(fe, "src", nt), de(L, fe);
        }, wr = (L) => {
          var fe = Qn(), br = we(fe);
          pt(br, "src", Kn), de(L, fe);
        };
        dt(_r, (L) => {
          nt ? L(gr) : L(wr, !1);
        });
      }
      ir(Le, (L) => I(k, L), () => b(k)), Bt(
        (L) => {
          ge = nr(S, 1, "container svelte-13k5vl5", null, ge, L), it = ar(S, "", it, { "--z-index": d() });
        },
        [() => ({ fixed: !s() })],
        Qe
      ), de(h, S);
    };
    dt(dr, (h) => {
      o() ? h(vr) : h(hr, !1);
    });
  }
  de(e, at), Dt();
}
Tn(["click"]);
const ea = (e) => {
  if (!e) throw new Error("Widget settings are required");
  const {
    adapter: t,
    beta: r,
    consumer: n,
    customLabel: a,
    hasHeader: i,
    hasOutsideClick: o,
    isIframe: u,
    isInternal: s,
    origin: l,
    parentId: d,
    platform: c,
    projectId: f,
    theme: v,
    tld: g,
    uid: m,
    zIndex: E
  } = e;
  if (!f && !n)
    throw new Error("Either projectId or consumer is required");
  const A = d ? document.getElementById(d) : null;
  In($n, {
    target: A ?? document.body,
    props: {
      adapter: t,
      beta: r,
      consumer: n,
      customLabel: a,
      hasHeader: i,
      hasOutsideClick: o,
      isIframe: u,
      isInternal: s,
      customOrigin: l,
      parentId: d,
      platform: c,
      projectId: f,
      theme: v,
      tld: g,
      uid: m,
      zIndex: E
    }
  });
};
window.initNeuroexpert = ea;
window.createNeuroexpertAdapter = Hn;
export {
  ea as initNeuroexpert
};
