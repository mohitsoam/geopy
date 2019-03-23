import re
from urllib.parse import urlencode

from geopy import exc
from geopy.geocoders.base import DEFAULT_SENTINEL, Geocoder
from geopy.location import Location
from geopy.util import logger

__all__ = ("What3Words", )


class What3Words(Geocoder):
    """What3Words geocoder.

    Documentation at:
        https://docs.what3words.com/api/v2/
    """

    multiple_word_re = re.compile(
        r"[^\W\d\_]+\.{1,1}[^\W\d\_]+\.{1,1}[^\W\d\_]+$", re.U
        )

    geocode_path = '/v2/forward'
    reverse_path = '/v2/reverse'

    def __init__(
            self,
            api_key,
            *,
            timeout=DEFAULT_SENTINEL,
            proxies=DEFAULT_SENTINEL,
            user_agent=None,
            ssl_context=DEFAULT_SENTINEL,
    ):
        """

        :param str api_key: Key provided by What3Words
            (https://accounts.what3words.com/register).

        :param int timeout:
            See :attr:`geopy.geocoders.options.default_timeout`.

        :param dict proxies:
            See :attr:`geopy.geocoders.options.default_proxies`.

        :param str user_agent:
            See :attr:`geopy.geocoders.options.default_user_agent`.

        :type ssl_context: :class:`ssl.SSLContext`
        :param ssl_context:
            See :attr:`geopy.geocoders.options.default_ssl_context`.
        """
        super().__init__(
            scheme='https',
            timeout=timeout,
            proxies=proxies,
            user_agent=user_agent,
            ssl_context=ssl_context,
        )

        self.api_key = api_key
        domain = 'api.what3words.com'
        self.geocode_api = '%s://%s%s' % (self.scheme, domain, self.geocode_path)
        self.reverse_api = '%s://%s%s' % (self.scheme, domain, self.reverse_path)

    def _check_query(self, query):
        """
        Check query validity with regex
        """
        if not self.multiple_word_re.match(query):
            return False
        else:
            return True

    def geocode(
            self,
            query,
            *,
            lang='en',
            exactly_one=True,
            timeout=DEFAULT_SENTINEL,
    ):

        """
        Return a location point for a `3 words` query. If the `3 words` address
        doesn't exist, a :class:`geopy.exc.GeocoderQueryError` exception will be
        thrown.

        :param str query: The 3-word address you wish to geocode.

        :param str lang: two character language codes as supported by
            the API (https://docs.what3words.com/api/v2/#lang).

        :param bool exactly_one: Return one result or a list of results, if
            available. Due to the address scheme there is always exactly one
            result for each `3 words` address, so this parameter is rather
            useless for this geocoder.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.

        :rtype: :class:`geopy.location.Location` or a list of them, if
            ``exactly_one=False``.
        """

        if not self._check_query(query):
            raise exc.GeocoderQueryError(
                "Search string must be 'word.word.word'"
            )

        params = {
            'addr': query,
            'lang': lang.lower(),
            'key': self.api_key,
        }

        url = "?".join((self.geocode_api, urlencode(params)))
        logger.debug("%s.geocode: %s", self.__class__.__name__, url)
        return self._parse_json(
            self._call_geocoder(url, timeout=timeout),
            exactly_one=exactly_one
        )

    def _parse_json(self, resources, exactly_one=True):
        """
        Parse type, words, latitude, and longitude and language from a
        JSON response.
        """

        code = resources['status'].get('code')

        if code:
            # https://docs.what3words.com/api/v2/#errors
            exc_msg = "Error returned by What3Words: %s" % resources['status']['message']
            if code == 401:
                raise exc.GeocoderAuthenticationFailure(exc_msg)

            raise exc.GeocoderQueryError(exc_msg)

        def parse_resource(resource):
            """
            Parse record.
            """

            if 'geometry' in resource:
                words = resource['words']
                position = resource['geometry']
                latitude, longitude = position['lat'], position['lng']
                if latitude and longitude:
                    latitude = float(latitude)
                    longitude = float(longitude)

                return Location(words, (latitude, longitude), resource)
            else:
                raise exc.GeocoderParseError('Error parsing result.')

        location = parse_resource(resources)
        if exactly_one:
            return location
        else:
            return [location]

    def reverse(
            self,
            query,
            *,
            lang='en',
            exactly_one=True,
            timeout=DEFAULT_SENTINEL,
    ):
        """
        Return a `3 words` address by location point. Each point on surface has
        a `3 words` address, so there's always a non-empty response.

        :param query: The coordinates for which you wish to obtain the 3 word
            address.
        :type query: :class:`geopy.point.Point`, list or tuple of ``(latitude,
            longitude)``, or string as ``"%(latitude)s, %(longitude)s"``.

        :param str lang: two character language codes as supported by the
            API (https://docs.what3words.com/api/v2/#lang).

        :param bool exactly_one: Return one result or a list of results, if
            available. Due to the address scheme there is always exactly one
            result for each `3 words` address, so this parameter is rather
            useless for this geocoder.

        :param int timeout: Time, in seconds, to wait for the geocoding service
            to respond before raising a :class:`geopy.exc.GeocoderTimedOut`
            exception. Set this only if you wish to override, on this call
            only, the value set during the geocoder's initialization.

        :rtype: :class:`geopy.location.Location` or a list of them, if
            ``exactly_one=False``.

        """
        lang = lang.lower()

        params = {
            'coords': self._coerce_point_to_string(query),
            'lang': lang.lower(),
            'key': self.api_key,
        }

        url = "?".join((self.reverse_api, urlencode(params)))

        logger.debug("%s.reverse: %s", self.__class__.__name__, url)
        return self._parse_reverse_json(
            self._call_geocoder(url, timeout=timeout),
            exactly_one=exactly_one
        )

    def _parse_reverse_json(self, resources, exactly_one=True):
        """
        Parses a location from a single-result reverse API call.
        """
        return self._parse_json(resources, exactly_one)
