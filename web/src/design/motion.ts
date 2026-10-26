import type { Transition, Variants } from 'motion/react'

export const ease = {
  out: [0.22, 1, 0.36, 1] as const,        // expressive deceleration
  inOut: [0.65, 0, 0.35, 1] as const,
  soft: [0.4, 0, 0.2, 1] as const,
}

export const dur = {
  instant: 0.12,
  fast: 0.2,
  base: 0.35,
  slow: 0.6,
  cinematic: 1.1,
}

export const spring = {
  snappy: { type: 'spring', stiffness: 520, damping: 34, mass: 0.7 } as Transition,
  smooth: { type: 'spring', stiffness: 260, damping: 30, mass: 0.9 } as Transition,
  soft:   { type: 'spring', stiffness: 140, damping: 22, mass: 1 } as Transition,
  layout: { type: 'spring', stiffness: 380, damping: 36, mass: 0.8 } as Transition,
}

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16, filter: 'blur(6px)' },
  show: {
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { duration: dur.base, ease: ease.out },
  },
  exit: {
    opacity: 0,
    y: -8,
    filter: 'blur(4px)',
    transition: { duration: dur.fast, ease: ease.inOut },
  },
}

export const stagger = (child = 0.055, delay = 0.05): Variants => ({
  hidden: {},
  show: {
    transition: {
      staggerChildren: child,
      delayChildren: delay,
    },
  },
  exit: {
    transition: {
      staggerChildren: 0.02,
      staggerDirection: -1,
    },
  },
})

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 24, scale: 0.985, filter: 'blur(10px)' },
  enter: {
    opacity: 1,
    y: 0,
    scale: 1,
    filter: 'blur(0px)',
    transition: { duration: dur.slow, ease: ease.out },
  },
  exit: {
    opacity: 0,
    y: -12,
    scale: 0.995,
    filter: 'blur(6px)',
    transition: { duration: dur.fast, ease: ease.inOut },
  },
}

export const modalVariants: Variants = {
  hidden: { opacity: 0, scale: 0.94, y: 12 },
  show: { opacity: 1, scale: 1, y: 0, transition: spring.smooth },
  exit: { opacity: 0, scale: 0.97, y: 6, transition: { duration: dur.fast, ease: ease.inOut } },
}

export const drawerVariants: Variants = {
  hidden: { x: '100%' },
  show: { x: 0, transition: spring.smooth },
  exit: { x: '100%', transition: { duration: dur.base, ease: ease.inOut } },
}

export const press = {
  whileHover: { y: -1 },
  whileTap: { scale: 0.97 },
  transition: spring.snappy,
}
