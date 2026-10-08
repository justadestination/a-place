// Generated from ../policy.generated.json by make_policy.py.
// Edit the JSON, re-run walkthrough.py --demo, then re-run this.
window.__POLICY__ = {
  "version": "1.0",
  "reader": {
    "interests": [
      {
        "topic": " protocol design",
        "weight": 0.5
      },
      {
        "topic": "typography",
        "weight": 0.5
      },
      {
        "topic": "print zines",
        "weight": 0.5
      },
      {
        "topic": "steganography",
        "weight": 0.5
      }
    ],
    "disinterests": [],
    "language": [
      "en-US",
      "en"
    ],
    "attentionProfile": {
      "chronotype": "normal",
      "deepWorkWindows": [
        {
          "days": [
            "mon",
            "tue",
            "wed",
            "thu",
            "fri",
            "sat",
            "sun"
          ],
          "start": "11:00",
          "end": "15:59 local",
          "timezone": "UTC"
        }
      ],
      "interruptionTolerance": 0
    }
  },
  "focus": {
    "tiers": {
      "ambient": {
        "enabled": true,
        "maxHeldItems": 200
      },
      "deferred": {
        "enabled": true,
        "rhythm": "daily",
        "deliveryWindows": [],
        "bundleThreshold": 5
      },
      "interrupting": {
        "enabled": false,
        "requiresEarnedTrust": true,
        "minTrustScore": 0.9,
        "hardDeadlineRequired": true,
        "verifiedAgainstReaderIntent": true,
        "dailyCap": 1,
        "suppressDuringDeepWork": true
      }
    },
    "budget": {
      "period": "week",
      "interruptionAllowance": 0,
      "overflowBehaviour": "hold-for-next-period"
    },
    "accounting": {
      "showWeeklyLedger": true,
      "surfaceHeldItems": true,
      "logAdaptations": true
    }
  },
  "authority": {
    "default": "surface",
    "perSource": [],
    "sendRequiresConfirmation": true
  },
  "privacy": {
    "privateZones": [
      {
        "match": "~/Mail/**",
        "rule": "no-read",
        "reason": "mine, not for summarising"
      },
      {
        "match": "~/health/**",
        "rule": "no-forward",
        "reason": "personal"
      }
    ],
    "readerModel": {
      "format": "markdown-directory",
      "location": "/opt/shadenet/reader-model",
      "exportable": true,
      "deletable": true
    }
  },
  "limits": [
    "Never send anything in my name without showing me the exact text first.",
    "Never use engagement metrics, streaks or unread counts on any surface."
  ],
  "constraints": [
    "No streaks, unread counts, or engagement metrics.",
    "No metric in this system may improve by interrupting the reader more often.",
    "Every stateful feature must degrade to a static readable document.",
    "Inference may never touch authority, private zones or hard limits.",
    "Presentation floors are locked: the render layer refuses violations rather than shipping them."
  ],
  "presentation": {
    "zoom": {
      "rootFontPx": 19,
      "scale": 1.1,
      "lineHeight": 1.6,
      "measureCh": 68
    },
    "fontFace": [
      "Iowan Old Style",
      "Charter",
      "Georgia"
    ],
    "contrast": {
      "minimumRatio": 9.0,
      "minimumRatioDark": 8.0,
      "enforceOnAllSurfaces": true,
      "darkMode": "auto",
      "locked": true
    },
    "density": {
      "clutterCeiling": 3,
      "modulesPerSurface": 5,
      "alwaysCollapseSecondary": true
    },
    "motion": {
      "reduceMotion": true,
      "allowParallax": false,
      "allowAutoPlay": false,
      "locked": true
    }
  },
  "inference": {
    "mayInferWithoutAsking": true,
    "inferred": [
      {
        "about": "which topics are worth this reader's time",
        "conclusion": "interests = protocol design, typography, print zines, steganography",
        "confidence": 0.9,
        "evidence": [
          "s1:open:1: read protocol design, typography",
          "s1:open:2: read protocol design",
          "s5:open:1: read protocol design, steganography",
          "s1:open:1: read protocol design, typography",
          "s2:open:1: read typography",
          "s3:open:1: read print zines",
          "s5:open:1: read protocol design, steganography"
        ],
        "contradictedBy": null
      },
      {
        "about": "when this reader is actually reachable",
        "conclusion": "chronotype = normal",
        "confidence": 0.7,
        "evidence": [
          "s1:open:1: opened at 10:00, stayed 600s",
          "s1:open:2: opened at 10:00, stayed 900s",
          "s2:open:1: opened at 11:00, stayed 45s",
          "s3:open:1: opened at 11:00, stayed 30s",
          "s5:open:1: opened at 09:00, stayed 50s",
          "conflicting observations present: late (2x)"
        ],
        "contradictedBy": null
      },
      {
        "about": "which hours are protected as deep work",
        "conclusion": "avoid interrupting during 11:00-15:59 local",
        "confidence": 0.6,
        "evidence": [
          "s2:open:2: opened and left in 20s",
          "s3:open:1: opened and left in 30s",
          "s4:open:1: opened and left in 25s"
        ],
        "contradictedBy": null
      },
      {
        "about": "which language the reader wants",
        "conclusion": "language = en-US, en, de",
        "confidence": 0.55,
        "evidence": [
          "s5:locale: browser sent Accept-Language en-US,en;q=0.9",
          "s6:locale: browser sent Accept-Language en-US,en;q=0.9,de;q=0.4"
        ],
        "contradictedBy": null
      },
      {
        "about": "what delivery rhythm this reader actually keeps up with",
        "conclusion": "deferred rhythm = daily (median gap 26h between deliveries)",
        "confidence": 0.71,
        "evidence": [
          "s1:deliver:1: arrived 24h after the previous delivery",
          "s2:deliver:1: arrived 24h after the previous delivery",
          "s3:deliver:1: arrived 72h after the previous delivery",
          "s4:deliver:1: arrived 26h after the previous delivery"
        ],
        "contradictedBy": null
      },
      {
        "about": "how interrupt-tolerant this reader is",
        "conclusion": "interruptionTolerance = 1 (4 of 5 interruptions dismissed unread)",
        "confidence": 0.8,
        "evidence": [
          "s1:interrupt:1: interrupted, reader dismissed",
          "s2:interrupt:1: interrupted, reader dismissed",
          "s3:interrupt:1: interrupted, reader dismissed",
          "s4:interrupt:1: interrupted, reader opened",
          "s5:interrupt:1: interrupted, reader dismissed"
        ],
        "contradictedBy": null
      }
    ],
    "correctable": true,
    "askThreshold": "high-stakes",
    "neverInfer": [
      "privacy zones",
      "hard limits",
      "authority grants"
    ]
  }
};
