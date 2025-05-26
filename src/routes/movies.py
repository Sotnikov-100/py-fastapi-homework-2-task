from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.database import get_db
from src.database.models import (
    MovieModel,
    CountryModel,
    GenreModel,
    ActorModel,
    LanguageModel,
)
from src.schemas.movies import (
    MovieListResponse,
    MovieListItem,
    MovieCreate,
    MovieDetailSchema,
    MovieUpdate,
    MovieUpdateResponse,
)

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get("/", response_model=MovieListResponse)
async def list_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * per_page

    total_count = await db.scalar(select(func.count(MovieModel.id)))
    if not total_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No movies found."
        )

    total_pages = (total_count + per_page - 1) // per_page

    result = await db.execute(
        select(MovieModel).order_by(MovieModel.id.desc()).offset(offset).limit(per_page)
    )
    movies = result.scalars().all()
    if not movies:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No movies found."
        )

    movie_items = [
        MovieListItem(
            id=movie.id,
            name=movie.name,
            date=movie.date,
            score=movie.score,
            overview=movie.overview,
        )
        for movie in movies
    ]

    prev_page = (
        f"/theater/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    )
    next_page = (
        f"/theater/movies/?page={page + 1}&per_page={per_page}"
        if page < total_pages
        else None
    )

    return MovieListResponse(
        movies=movie_items,
        prev_page=prev_page,
        next_page=next_page,
        total_pages=total_pages,
        total_items=total_count,
    )


@router.post("/", response_model=MovieDetailSchema, status_code=status.HTTP_201_CREATED)
async def create_movie(
    movie_data: MovieCreate,
    db: AsyncSession = Depends(get_db),
):
    existing_movie = await db.scalar(
        select(MovieModel)
        .where(MovieModel.name == movie_data.name)
        .where(MovieModel.date == movie_data.date)
    )
    if existing_movie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A movie with the name '{movie_data.name}' and release date '{movie_data.date}' already exists.",
        )

    country = await db.scalar(
        select(CountryModel).where(CountryModel.code == movie_data.country)
    )
    if not country:
        country = CountryModel(code=movie_data.country, name=None)
        db.add(country)
        await db.flush()

    genres = []
    for genre_name in movie_data.genres:
        genre = await db.scalar(select(GenreModel).where(GenreModel.name == genre_name))
        if not genre:
            genre = GenreModel(name=genre_name)
            db.add(genre)
            await db.flush()
        genres.append(genre)

    actors = []
    for actor_name in movie_data.actors:
        actor = await db.scalar(select(ActorModel).where(ActorModel.name == actor_name))
        if not actor:
            actor = ActorModel(name=actor_name)
            db.add(actor)
            await db.flush()
        actors.append(actor)

    languages = []
    for lang_name in movie_data.languages:
        language = await db.scalar(
            select(LanguageModel).where(LanguageModel.name == lang_name)
        )
        if not language:
            language = LanguageModel(name=lang_name)
            db.add(language)
            await db.flush()
        languages.append(language)

    movie = MovieModel(
        name=movie_data.name,
        date=movie_data.date,
        score=movie_data.score,
        overview=movie_data.overview,
        status=movie_data.status,
        budget=movie_data.budget,
        revenue=movie_data.revenue,
        country_id=country.id,
    )
    movie.genres.extend(genres)
    movie.actors.extend(actors)
    movie.languages.extend(languages)

    db.add(movie)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input data."
        )

    result = await db.execute(
        select(MovieModel)
        .options(
            selectinload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        )
        .where(MovieModel.id == movie.id)
    )
    movie_with_relationships = result.scalar_one()

    return movie_with_relationships


@router.get("/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.scalar(
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
        )
        .where(MovieModel.id == movie_id)
    )
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    return movie


@router.delete("/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Movie with the given ID was not found.",
        )
    await db.delete(movie)
    await db.commit()
    return None


async def _update_movie_country(
    db: AsyncSession, movie: MovieModel, country_code: str
) -> None:
    country = await db.scalar(
        select(CountryModel).where(CountryModel.code == country_code)
    )
    if not country:
        country = CountryModel(code=country_code, name=None)
        db.add(country)
        await db.flush()
    movie.country_id = country.id


async def _update_movie_relationships(
    db: AsyncSession,
    movie: MovieModel,
    model: type[GenreModel | ActorModel | LanguageModel],
    names: list[str],
    relationship_attr: str,
) -> None:
    items = []
    for name in names:
        item = await db.scalar(select(model).where(model.name == name))
        if not item:
            item = model(name=name)
            db.add(item)
            await db.flush()
        items.append(item)
    setattr(movie, relationship_attr, items)


@router.patch("/{movie_id}/", response_model=MovieUpdateResponse)
async def update_movie(
    movie_id: int,
    movie_data: MovieUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    movie = await db.get(MovieModel, movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    update_data = movie_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field not in {"genres", "actors", "languages", "country"}:
            setattr(movie, field, value)

    if "country" in update_data:
        await _update_movie_country(db, movie, update_data["country"])

    relationship_updates = {
        "genres": (GenreModel, "genres"),
        "actors": (ActorModel, "actors"),
        "languages": (LanguageModel, "languages"),
    }
    for key, (model, attr) in relationship_updates.items():
        if key in update_data:
            await _update_movie_relationships(db, movie, model, update_data[key], attr)

    if "name" in update_data or "date" in update_data:
        existing = await db.scalar(
            select(MovieModel)
            .where(MovieModel.name == movie.name)
            .where(MovieModel.date == movie.date)
            .where(MovieModel.id != movie_id)
        )
        if existing:
            raise HTTPException(
                409, detail="Movie with this name and date already exists"
            )

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(400, detail="Invalid data")

    return {"detail": "Movie updated successfully."}
