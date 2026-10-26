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
  const isInView = useInView(containerRef, { amount: 0.1 })
  const { resolvedTheme } = useTheme()

  // Mount video quickly
  useEffect(() => {
    if (reducedMotion) return
    setMounted(true)
  }, [reducedMotion])

  // If already buffered, mark as ready to play immediately
  useEffect(() => {
    if (videoRef.current && videoRef.current.readyState >= 2) {
      setCanPlay(true)
    }
  }, [mounted])

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
  // Smoothly dissolves the video into the surrounding page canvas on all sides.
  const maskStyle: React.CSSProperties = {
    maskImage:
      'radial-gradient(ellipse 85% 80% at 55% 50%, black 30%, rgba(0, 0, 0, 0.85) 60%, rgba(0, 0, 0, 0.25) 85%, transparent 100%)',
    WebkitMaskImage:
      'radial-gradient(ellipse 85% 80% at 55% 50%, black 30%, rgba(0, 0, 0, 0.85) 60%, rgba(0, 0, 0, 0.25) 85%, transparent 100%)',
  }

  const isDark = resolvedTheme === 'dark'

  return (
    <div
      ref={containerRef}
      className={`relative w-full aspect-[16/10] max-w-[640px] xl:max-w-[720px] flex items-center justify-center overflow-hidden pointer-events-none select-none ${className}`}
      aria-hidden="true"
    >
      {/* Soft atmospheric light glow behind the video */}
      <div
        className="absolute inset-0 pointer-events-none opacity-50 blur-[80px]"
        style={{
          background: isDark
            ? 'radial-gradient(ellipse at 55% 50%, rgba(56, 189, 248, 0.16) 0%, rgba(99, 102, 241, 0.1) 45%, transparent 75%)'
            : 'radial-gradient(ellipse at 55% 50%, rgba(99, 102, 241, 0.1) 0%, rgba(56, 189, 248, 0.06) 45%, transparent 75%)',
        }}
      />

      <div
        className="absolute inset-0 w-full h-full flex items-center justify-center"
        style={maskStyle}
      >
        {/* High-fidelity fallback / poster image */}
        <img
          src="/media/hero-poster.jpg"
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-700"
          style={{
            opacity: canPlay ? 0 : 0.95,
            filter: isDark
              ? 'brightness(1.05) contrast(1.05)'
              : 'invert(0.92) hue-rotate(180deg) brightness(1.15) contrast(1.05)',
          }}
        />

        {/* Real video layer */}
        {mounted && !reducedMotion && (
          <motion.video
            ref={videoRef}
            muted
            loop
            playsInline
            autoPlay
            preload="auto"
            onLoadedData={() => setCanPlay(true)}
            onCanPlay={() => setCanPlay(true)}
            onPlaying={() => setCanPlay(true)}
            initial={{ opacity: 0 }}
            animate={{
              opacity: canPlay ? (isDark ? 0.95 : 0.8) : 0,
            }}
            transition={{ duration: 0.7 }}
            className="absolute inset-0 w-full h-full object-cover"
            style={{
              filter: isDark
                ? 'brightness(1.05) contrast(1.08)'
                : 'invert(0.92) hue-rotate(180deg) brightness(1.15) contrast(1.08)',
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
