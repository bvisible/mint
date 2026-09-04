////// Neoffice — added file (no upstream equivalent): pins /mint in the Neoffice cockpit's
////// favourites (e38d1a6), through the desk's own favourite API. Upstream has no cockpit.
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk"
import { Star } from "lucide-react"
import _ from "@/lib/translate"

// Pin the Bank Reconciliation page to the NeoCockpit sidebar favorites,
// mirroring the desk page-head star (neoffice_theme/cockpit_favorites.js).
const FAV_ROUTE = "/mint"
const FAV_LABEL = "Bank Reconciliation"

const FavoriteStar = () => {
    const { data, mutate } = useFrappeGetCall<{ message: boolean }>(
        "neoffice_theme.cockpit_favorites.is_favorite",
        { route: FAV_ROUTE },
    )
    const { call, loading } = useFrappePostCall(
        "neoffice_theme.cockpit_favorites.toggle_favorite",
    )
    const isFav = !!data?.message

    const toggle = async () => {
        if (loading) return
        await call({ route: FAV_ROUTE, label: _(FAV_LABEL), fav_type: "Page", icon: "landmark" })
        mutate()
        // Ask the NeoCockpit sidebar to refresh its "Favoris" section.
        window.dispatchEvent(new CustomEvent("nf-favorites-changed"))
    }

    return (
        <button
            type="button"
            onClick={toggle}
            title={_(isFav ? "Remove from favorites" : "Add to favorites")}
            aria-label={_(isFav ? "Remove from favorites" : "Add to favorites")}
            className="inline-flex items-center justify-center h-7 w-7 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors cursor-pointer"
        >
            <Star size={16} className={isFav ? "fill-[#D68A59] text-[#D68A59]" : ""} />
        </button>
    )
}

export default FavoriteStar
