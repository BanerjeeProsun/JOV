import React, { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion, useInView } from 'motion/react'
import { useTheme } from '../ThemeProvider'

interface HeroVideoProps {
  className?: string
}

export const HeroVideo: React.FC<HeroVideoProps> = ({ className = '' }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [canPlay, setCanPlay] = useState(false)
  const [mounted, setMounted] = useState(false)
  const reducedMotion = useReducedMotion()
  const isInView = useInView(containerRef, { amount: 0.15 })
  const { resolvedTheme } = useTheme()

  // Defer video mount slightly to ensure instant first paint
  useEffect(() => {
    if (reducedMotion) return
    const timer = setTimeout(() => setMounted(true), 100)
    return () => clearTimeout(timer)
  }, [reducedMotion])

  // Play/pause based on viewport visibility to conserve GPU
  useEffect(() => {
    if (!videoRef.current || reducedMotion) return
    if (isInView && document.visibilityState === 'visible') {
      videoRef.current.play().catch(() => {})
    } else {
      videoRef.current.pause()
    }
  }, [isInView, mounted, reducedMotion])

  useEffect(() => {
    const handleVisibility = () => {
      if (!videoRef.current || reducedMotion) return
      if (document.visibilityState === 'visible' && isInView) {
        videoRef.current.play().catch(() => {})
      } else {
        videoRef.current.pause()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [isInView, reducedMotion])

  // Multi-directional gradient mask:
  // Smoothly dissolves the video into the surrounding page canvas on all sides,
  // especially fading out on the left where it meets the typographic hero copy.
  const maskStyle: React.CSSProperties = {
    maskImage:
      'radial-gradient(ellipse 75% 70% at 65% 50%, black 20%, rgba(0, 0, 0, 0.75) 50%, rgba(0, 0, 0, 0.2) 75%, transparent 95%)',
    WebkitMaskImage:
      'radial-gradient(ellipse 75% 70% at 65% 50%, black 20%, rgba(0, 0, 0, 0.75) 50%, rgba(0, 0, 0, 0.2) 75%, transparent 95%)',
  }

  const isDark = resolvedTheme === 'dark'

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full min-h-[420px] lg:min-h-[560px] flex items-center justify-center overflow-hidden pointer-events-none select-none ${className}`}
      aria-hidden="true"
    >
      {/* Soft ambient light backdrop behind the video to enhance atmospheric depth */}
      <div
        className="absolute inset-0 pointer-events-none opacity-40 blur-[90px]"
        style={{
          background: isDark
            ? 'radial-gradient(ellipse at 60% 50%, rgba(56, 189, 248, 0.12) 0%, rgba(99, 102, 241, 0.08) 40%, transparent 70%)'
            : 'radial-gradient(ellipse at 60% 50%, rgba(99, 102, 241, 0.08) 0%, rgba(56, 189, 248, 0.05) 40%, transparent 70%)',
        }}
      />

      <div
        className="relative w-full h-full flex items-center justify-center"
        style={maskStyle}
      >
        {/* High-fidelity fallback / poster image */}
        <img
          src="/media/hero-poster.jpg"
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-1000"
          style={{
            opacity: canPlay ? 0 : isDark ? 0.85 : 0.45,
            filter: isDark
              ? 'brightness(0.95) contrast(1.05)'
              : 'invert(0.92) hue-rotate(180deg) brightness(1.15) contrast(1.05)',
          }}
        />

        {/* Video layer */}
        {mounted && !reducedMotion && (
          <motion.video
            ref={videoRef}
            muted
            loop
            playsInline
            autoPlay
            preload="auto"
            onCanPlay={() => setCanPlay(true)}
            initial={{ opacity: 0 }}
            animate={{
              opacity: canPlay ? (isDark ? 0.9 : 0.6) : 0,
            }}
            transition={{ duration: 0.9 }}
            className="absolute inset-0 w-full h-full object-cover"
            style={{
              filter: isDark
                ? 'brightness(0.95) contrast(1.08)'
                : 'invert(0.92) hue-rotate(180deg) brightness(1.15) contrast(1.08)',
              mixBlendMode: isDark ? 'screen' : 'multiply',
            }}
          >
            <source src="/media/hero-video.webm" type="video/webm" />
            <source src="/media/hero-video.mp4" type="video/mp4" />
          </motion.video>
        )}
      </div>
    </div>
  )
}
