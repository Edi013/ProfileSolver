package org.example.controller;

import org.example.model.Company;
import org.example.repository.CompanyRepository;
import org.example.services.SearchService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class CompanyController {

    private final SearchService searchService;

    public CompanyController(SearchService searchService) {
        this.searchService = searchService;
    }

    @GetMapping("/api/companies/search")
    public List<Company> searchCompanies(@RequestParam String query) {
        return searchService.searchCompanies(query);
    }
}
